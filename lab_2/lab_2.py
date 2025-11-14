from httpcore import TimeoutException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from multiprocessing import Pool, freeze_support
from itertools import repeat
from fake_useragent import UserAgent
from random import uniform
from time import sleep


class TranslationSelectors:
    OUTPUT_TEXT = 'span.ryNqvb'
    OUTPUT_TEXT_ALT = 'span.HwtZe'
    INPUT_FIELD = 'textarea.er8xn'


class PoFileConstants:
    MSGID_PREFIX_LENGTH = len('msgid ""\n')  # 9
    MSGSTR_PREFIX_LENGTH = len('msgstr ""\n')  # 10
    MIN_TRANSLATED_LENGTH = 2


class TextPreprocessor:
    """Класс для подготовки текста к переводу"""

    @staticmethod
    def extract_formats(text: str) -> tuple[str, list, list, bool, bool]:
        """
        Извлекает форматирование из текста
        Returns: (обработанный_текст, переменные, классы, unf, service_f)
        """
        substitution, substitution2 = "{%s}", "{+}"
        variables, classes = [], []
        unf = service_f = False

        # Check python unnamed-format
        if '%s' in text:
            unf = True

        # Save python named-format
        count_format = text.count('%(')
        for i in range(count_format):
            f_pos = text.find('%(')
            s_pos = text[f_pos:].find(')s')
            named_format = text[f_pos:][:s_pos + 2]  # + ')s'
            variables.append(named_format)
            text = text.replace(named_format, substitution % (i + 1,), 1)

        # Prepare string to work
        if r'\"' in text:
            service_f = True
            text = text.replace(r'\"', '"')

        # Save html classes
        count_classes = text.count('class="')
        for i in range(count_classes):
            f_pos = text.find('class="')
            s_pos = text[f_pos + 7:].find('"')
            cls = f'class="{text[f_pos + 7:][:s_pos]}"'
            text = text.replace(cls, substitution2, 1)
            classes.append(cls)

        return text, variables, classes, unf, service_f

    @staticmethod
    def restore_formats(translated_text: str, variables: list,
                        classes: list, unf: bool, service_f: bool) -> str:
        """Восстанавливает форматирование в переведенном тексте"""
        substitution, substitution2 = "{%s}", "{+}"

        # Fix python unnamed-format
        if unf:
            translated_text = translated_text.replace('%S', '%s')

        # Return python named-format
        for i in range(len(variables)):
            translated_text = translated_text.replace(
                substitution % (i + 1,), variables[i], 1)

        # Return html classes
        for i in range(len(classes)):
            translated_text = translated_text.replace(
                substitution2, classes[i], 1)

        # Fix python service str
        if service_f:
            translated_text = translated_text.replace('"', r'\"')

        return translated_text


class TranslationClient:
    """Класс для работы с переводчиком через Selenium"""

    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def take_text(self) -> str:
        """
        Получает текст из поля вывода
        NoSuchElementException thrown if the page didn't load correctly
        """
        random_pause()
        try:
            trans_text = self.driver.find_elements(
                by=By.CSS_SELECTOR, value=TranslationSelectors.OUTPUT_TEXT)
        except NoSuchElementException:
            self.driver.refresh()
            trans_text = self.driver.find_elements(
                by=By.CSS_SELECTOR, value=TranslationSelectors.OUTPUT_TEXT)

        if not trans_text:  # Multiple translations
            trans_text = self.driver.find_elements(
                by=By.CSS_SELECTOR, value=TranslationSelectors.OUTPUT_TEXT_ALT)[-1:]

        trans_text = [sentence.text for sentence in trans_text]
        return ''.join(trans_text)

    def send_for_translation(self, text: str, last_trans: str) -> str:
        """Отправляет текст на перевод и возвращает результат"""
        self.driver.find_element(
            by=By.CSS_SELECTOR, value=TranslationSelectors.INPUT_FIELD).clear()
        self.driver.find_element(
            by=By.CSS_SELECTOR, value=TranslationSelectors.INPUT_FIELD).send_keys(text)

        trans = self.take_text()

        if trans == last_trans:  # If GT is late
            trans = self.take_text()

        return trans


class TranslationService:
    """Основной сервис перевода, координирующий работу препроцессора и клиента"""

    def __init__(self, driver: webdriver.Chrome):
        self.client = TranslationClient(driver)
        self.preprocessor = TextPreprocessor()

    def translate(self, text: str, last_trans: str, retry: int) -> str:
        """
        Основной метод перевода текста
        Args:
            text: Text to translate
            last_trans: Last translate
            retry: Attempts to translate

        Returns: Translated text
        """
        # Подготовка текста
        processed_text, variables, classes, unf, service_f = (
            self.preprocessor.extract_formats(text))

        # Перевод
        try:
            trans = self.client.send_for_translation(processed_text, last_trans)
        except (NoSuchElementException, TimeoutException) as ex:
            random_pause()
            if retry:
                print(f'[!] FAIL -> {text} | retry={retry} ({ex})')
                return self.translate(text, last_trans, retry - 1)
            else:
                print(f'[!] No attempts left for -> {text}')
                return ""

        # Восстановление форматирования
        trans = self.preprocessor.restore_formats(
            trans, variables, classes, unf, service_f)

        print(f'[+] {text} - {trans}')
        return trans


def random_pause():
    sleep(round(uniform(1.8, 2.1), 2))


def is_simple_translated(lines: list[str], i: int, s: str) -> bool:
    """Проверяет простой перевод (одна строка)"""
    if len(s) <= PoFileConstants.MSGID_PREFIX_LENGTH:
        return False
    try:
        next_str = lines[i + 1]
        return (next_str.startswith('msgstr "') and
                len(next_str) > PoFileConstants.MSGSTR_PREFIX_LENGTH)
    except IndexError:
        return False


def is_complex_translated(lines: list[str], i: int) -> bool:
    """Проверяет сложный перевод (многострочный)"""
    plus = 1
    while True:
        try:
            next_str = lines[i + plus]
            plus += 1
            if next_str.startswith('msgstr "'):
                next_str2 = lines[i + plus]
                return ((len(next_str) > 10) or
                        (next_str2.startswith('"') and
                         len(next_str2) > PoFileConstants.MIN_TRANSLATED_LENGTH))
        except IndexError:
            return False


def check_translated(lines: list[str], i: int, s: str) -> bool:
    """
    The method checks if the strings are translated
    Args:
        lines: All lines
        i: Current index of string
        s: Current string

    Returns: True if already translated
    """
    if s.startswith('msgid "'):
        return (is_simple_translated(lines, i, s) or
                is_complex_translated(lines, i))
    return False


def translate(dr: webdriver.Chrome, text: str,
              last_trans: str, retry: int) -> str:
    """
    This method translates received strings
    Args:
        dr: Driver
        text: Text to translate
        last_trans: Last translate
        retry: Attempts to translate

    Returns: Translated text
    """
    translation_service = TranslationService(dr)
    return translation_service.translate(text, last_trans, retry)


def translator(
        code: str,
        driver_path: str,
        locale_path: str,
        headless: bool,
        lang_interface: str,
        from_lang: str,
        retry: int
):
    """
    Initialization of all variables. And the translation.
    Args:
        code: Language code
        driver_path: Path to chromedriver
        locale_path: Path to locale folder
        headless: Windowless mode
        lang_interface: Language (code) in which GT will be opened
        from_lang: Language code from which the translation will be carried out
        retry: Attempts to translate

    Returns: None
    """
    url = ('https://translate.google.com/?hl='
           '%(lang_interface)s&sl=%(from_lang)s&tl='
           '%(to_lang)s&op=translate')
    user_agent = UserAgent()
    s = Service(executable_path=driver_path)
    options = webdriver.ChromeOptions()
    options.add_argument(argument=f'user-agent={user_agent.random}')
    options.add_argument(argument='--disable-blink-features'
                                  '=AutomationControlled')
    if headless:
        options.add_argument(argument='--headless')
    dr = webdriver.Chrome(service=s, options=options)
    solved_url = url % {'lang_interface': lang_interface,
                        'from_lang': from_lang,
                        'to_lang': code}
    dr.get(solved_url)
    modified = False

    # Read file
    path_file = f'{locale_path}/{code}/LC_MESSAGES/django.po'
    try:
        with open(path_file, 'r', encoding='UTF-8') as file:
            print(f'{path_file} - opened!')
            text = ''
            found = False
            translated = None
            next_complex = False
            save_complex = False
            last_trans = None
            to_translate = list()
            lines = file.readlines()
    except FileNotFoundError:
        print(f"[!] FAIL {path_file} doesn't exists")
        return

    # i - string index
    # s - the string
    for i, s in enumerate(lines):
        # Checking for already translated
        if check_translated(lines=lines, i=i, s=s):
            text += s
            continue

        if s.startswith('msgid "'):  # Define text for translation
            string_text = s[s.find('"') + 1:s.rfind('"')].strip()
            if string_text:  # Simple translation
                translated, found = translate(dr=dr,
                                              text=string_text,
                                              last_trans=last_trans,
                                              retry=retry), True
                last_trans = translated
            else:  # Complex trans
                if lines[i + 1].startswith('"'):  # It's complex text
                    next_complex = True
            text += s

        elif s.startswith('"') and next_complex and len(s) > 2:  # Complex text
            to_translate.append(s[s.find('"') + 1:s.rfind('"')])
            text += s
            # Check next line
            try:
                if lines[i + 1].startswith('msgstr "'):
                    next_complex, save_complex, found = False, True, True
            except IndexError:
                print(f'[!] SyntaxError at {i + 1} line in {path_file}')

        elif s.startswith('msgstr "') and found:  # Write translated text
            if save_complex:  # Write complex
                solved = translate(
                    dr=dr, text=' '.join(to_translate),
                    last_trans=last_trans, retry=retry)
                last_trans = solved
                text += ('msgstr ""\n"' + solved + '"\n')
                save_complex = False
                to_translate.clear()
            else:  # Save simple
                text += f'msgstr "{translated}"\n'
            modified = True
            translated, found = None, False
        else:  # Just text
            text += s

    # Dump
    if modified:
        with open(path_file, 'w', encoding='UTF-8') as file:
            file.write(text)
            print(path_file, '- Saved!')
    else:
        print(path_file, '- Without changes!')


def manager(codes: list,
            driver_path: str,
            locale_path: str,
            headless: bool = True,
            multi: bool = False,
            multi_max: int = 10,
            lang_interface: str = 'en',
            from_lang: str = 'en',
            retry: int = 3
            ):
    """
    The manager handles the multiprocessing mode
    Args:
        codes: Language codes
        driver_path: Path to chromedriver
        locale_path: Path to locale folder
        headless: Windowless Mode
        multi: Multiprocessor mode
        multi_max: Maximum number of processes
        lang_interface: Language (code) in which GT will be opened
        from_lang: Language code from which the translation will be carried out
        retry: Attempts to translate

    Returns: None
    """
    if multi:
        freeze_support()
        variables_copy = codes.copy()
        while variables_copy:
            langs = variables_copy[:multi_max]
            variables_copy = variables_copy[multi_max:]
            with Pool(processes=len(langs)) as pool:
                pool.starmap(translator, zip(langs,
                                             repeat(driver_path),
                                             repeat(locale_path),
                                             repeat(headless),
                                             repeat(lang_interface),
                                             repeat(from_lang),
                                             repeat(retry)))
    else:
        for code in codes:
            translator(
                code, driver_path,
                locale_path, headless,
                lang_interface, from_lang,
                retry)


if __name__ == '__main__':
    manager(
        codes=['de', 'fr', 'ja', 'tr', 'ru', 'uk'],
        driver_path='/DJTranslator/chromedriver',
        locale_path='/DJAuth/locale',
        multi=True,
        lang_interface='ru',
    )
