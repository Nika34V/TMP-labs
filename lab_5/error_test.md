# Error Test File

## Test Errors
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [Bad Title API](https://example.com) | first letter not capital | No | Yes | Yes |  <!-- Multiple errors -->
| [Another](https://example.com) | Good description. | `No` | Invalid | Unknown |  <!-- Invalid HTTPS -->
| [Test](https://example.com) | Short. | `No` | Yes | Invalid |  <!-- Invalid CORS, short description -->
| Missing column entry | Description here | `No` | Yes |  <!-- Missing column -->

## Another Category
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [Good API](https://good.example.com) | Perfect description here | `apiKey` | Yes | Yes |  <!-- This one is good -->
| [Another Good](https://example.com) | Another good description | `OAuth` | No | No |