# Mailto Scraper

A Python tool that extracts email addresses from a list of websites. It searches for emails both in the visible text and in mailto links, generating a comprehensive report of all found email addresses in CSV format.

## Features

- Extracts emails from multiple websites
- Reads URLs from a text file
- Searches in both visible text and mailto links
- Removes duplicate email addresses
- Generates detailed logs of the scraping process
- Handles errors gracefully
- Uses proper User-Agent headers to avoid blocking
- Configurable output directory for results
- Output in CSV format for better data handling
- Can be used in conjunction with shopify_searcher to process Shopify stores
- Advanced email validation:
  - Validates email format using email-validator library
  - Cleans and validates domain extensions
  - Removes invalid characters from domains
  - Detects and removes duplicate variations of the same email

## Installation

### Setting up a Virtual Environment

You have two options to set up your development environment:

#### Option 1: Using Poetry (Recommended)

1. Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Clone the repository:
```bash
git clone https://github.com/yourusername/mailto-scraper.git
cd mailto-scraper
```

3. Let Poetry create the virtual environment and install dependencies:
```bash
poetry install
```

4. To activate the virtual environment:
```bash
poetry shell
```

#### Option 2: Using venv (Python's built-in virtual environment)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mailto-scraper.git
cd mailto-scraper
```

2. Create a virtual environment:
```bash
python -m venv .venv
```

3. Activate the virtual environment:
- On Linux/macOS:
  ```bash
  source .venv/bin/activate
  ```
- On Windows:
  ```bash
  .venv\Scripts\activate
  ```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

### Verifying Installation

To verify that everything is set up correctly:
```bash
python -c "import requests, bs4, email_validator; print('Setup successful!')"
```

## Usage

1. Create a text file (e.g., `data/urls.txt`) with your target websites, one URL per line:
```text
https://example1.com
https://example2.com
# This is a comment and will be ignored
https://example3.com
```

2. Run the scraper:
- Basic usage (output files will be created in the current directory):
  ```bash
  poetry run python -m mailto_scraper.main urls.txt
  ```

- Using a relative path for output directory:
  ```bash
  poetry run python -m mailto_scraper.main data/urls.txt -o data/results
  ```

- Using an absolute path for output directory:
  ```bash
  poetry run python -m mailto_scraper.main data/urls.txt -o /home/user/scraping/results
  ```

- Get help on available options:
  ```bash
  poetry run python -m mailto_scraper.main --help
  ```

### Command Line Options

```
usage: python -m mailto_scraper.main [-h] [-o OUTPUT_DIR] urls_file

Extract email addresses from a list of websites.

positional arguments:
  urls_file             Text file containing URLs to process (one per line)

optional arguments:
  -h, --help           show this help message and exit
  -o, --output-dir     Directory where output files will be saved (default: current directory)
```

### Output Files

The script generates two files in the specified output directory (or current directory if not specified):

- `found_emails_YYYYMMDD_HHMMSS.csv`: Contains all unique valid email addresses found in CSV format
- `scraping_results_YYYYMMDD_HHMMSS.log`: Detailed log of the scraping process, including:
  - Processed URLs
  - Found and discarded emails
  - Domain cleaning operations
  - Validation results
  - Success/failure for each URL

### Email Validation Process

The tool performs several validation steps:
1. Extracts potential email addresses using regex
2. Cleans and normalizes the email format
3. Validates the domain structure and extension
4. Performs RFC compliance check using email-validator
5. Removes duplicate variations of the same email
6. Cleans invalid characters from domain parts

### Input File Format

- One URL per line
- Empty lines are ignored
- Lines starting with # are treated as comments and ignored
- URLs should include the protocol (http:// or https://)

## Requirements

- Python 3.8 or higher
- Dependencies (automatically installed by Poetry or pip):
  - requests
  - beautifulsoup4
  - email-validator
  - pytest (for development)

## Development

To run tests:
```bash
# With Poetry
poetry run pytest

# With venv
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Author

Pere Pasamonte - [perepc@gmail.com]

## Using shopify_searcher

The repository includes a complementary tool called `shopify_searcher` that helps you find Shopify stores with specific characteristics. Currently, it's configured to find stores that are likely using the judge.me review system.

### Basic Usage

To use shopify_searcher:

```bash
poetry run python -m shopify_searcher.main
```

The tool will:
1. Search for Shopify stores with specific characteristics
2. Generate a list of URLs in the data directory
3. Create a detailed log of the search process in the data directory too

Note: Currently, the tool doesn't accept command-line arguments, and paramenters have to be set in the code; those are the default values:

- output_dir: 'data'
- num_results: 100
- region: 'es'
- lang: 'es'
- unique: True
- sleep_interval: 5
- save_results: True

The generated URLs file can then be used as input for the mailto_scraper:

```bash
poetry run python -m mailto_scraper.main
``` 