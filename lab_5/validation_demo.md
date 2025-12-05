# API Validation Demo

## Demo Category
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [Perfect API](https://perfect.example.com) | This is a perfectly valid API entry with good description | `No` | Yes | Yes |
| [API With Warning](https://warning.example.com) | Short desc | `No` | Yes | Yes |  <!-- Warning: description too short -->
| [Bad Auth Format](https://auth.example.com) | Good description here | No | Yes | Yes |  <!-- Error: auth without backticks -->
| [Invalid HTTPS](https://https.example.com) | Another good description | `No` | Maybe | Yes |  <!-- Error: invalid HTTPS value -->
| [Title Issue API](https://title.example.com) | Description for testing | `apiKey` | Yes | Unknown |  <!-- Error: title ends with API -->
| [Bad Description](https://desc.example.com) | first letter lowercase | `OAuth` | No | No |  <!-- Error: description not capitalized -->
| [Mixed Case](https://mixed.example.com) | Good ending with period. | `User-Agent` | Yes | Yes |  <!-- Error: description ends with punctuation -->