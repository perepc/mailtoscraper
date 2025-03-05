# Mailto Scraper

A comprehensive Python toolkit for email marketing automation. It includes tools for finding email addresses from websites, generating personalized email content, and sending emails. The toolkit consists of several specialized modules:

## Core Modules

### 1. Mailto Scraper
- Extracts email addresses from multiple websites
- Searches in both visible text and mailto links
- Advanced email validation and cleaning
- Generates detailed logs of the scraping process
- Handles errors gracefully
- Uses proper User-Agent headers
- Configurable output directory
- Output in JSON format for better data handling

### 2. Email Writer
- Generates personalized email content using AI
- Analyzes company websites to understand their business
- Creates tailored email subjects and bodies
- Uses Perplexity AI for content generation
- Supports HTML formatting in email bodies
- Includes customizable email templates
- Handles multiple email generation in batch
- Generates detailed logs of content generation

### 3. Email Sender
- Sends emails using the Resend API
- Supports HTML email content
- Handles batch email sending
- Provides detailed sending logs
- Tracks successful and failed sends
- Includes retry mechanisms
- Configurable sending parameters

### 4. Shopify Searcher
- Finds Shopify stores using specific criteria
- Supports searching by region and language
- Detects stores using Judge.me reviews
- Handles store redirects and personal domains
- Includes retry mechanisms with exponential backoff
- Generates detailed search logs
- Configurable search parameters
- Can exclude specific URLs

## Features

- Complete email marketing automation pipeline
- Advanced email validation and cleaning
- AI-powered content generation
- Detailed logging for all operations
- Error handling and retry mechanisms
- Configurable output formats and directories
- Support for batch operations
- Region and language-specific searching

## Installation

### Setting up a Virtual Environment Using Poetry

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

### Verifying Installation

To verify that everything is set up correctly:
```bash
python -c "import requests, bs4, email_validator, langchain; print('Setup successful!')"
```

### Configuring environment variables

Create a `.env` file in the root of the project with the following variables:
```
PERPLEXITY_API_KEY=your_perplexity_api_key
PERPLEXITY_API_URL=https://api.perplexity.ai/chat/completions
PERPLEXITY_MODEL=sonar
RESEND_API_KEY=your_resend_api_key
RESEND_API_URL=https://api.resend.com/emails
MAIL_FROM=your_sender_email
```

## Usage

### 1. Finding Shopify Stores

For my particular use case, I have a list of Shopify stores that I want to find email addresses for. I have created a script that scrapes the Shopify stores and saves the results in a json file.

As it uses Google Custom Search API, you need to create a custom search engine and get json credentials from Google Cloud Console. Follow the instructions in the [shopify_searcher README](src/shopify_searcher/README.md).

1. Search for Shopify stores:
```bash
poetry run python -m shopify_searcher.main --region es --lang es --output_dir data
```

### 2. Finding Email Addresses

1. Create a json file (e.g., `data/shopify_stores_20250304_083013.json`) with your target websites (this is the output of the shopify searcher or you can use your own list just filling the custom_domain attribute):
```json
[
    {
        "custom_domain": "https://example1.com",
        "shopify_url": "",
        "email": "",
        "region": "",
        "lang": ""
    }
]
```

2. Run the scraper:
```bash
poetry run python -m mailto_scraper.main --input_file data/shopify_stores_20250304_083013.json --output_dir data
```

### 3. Generating Email Content

1. Use the email writer to generate personalized content:
```bash
poetry run python -m email_writer.main --json_file data/emails.json --output_dir data/content --my_company_url https://mycompany.com
```

### 4. Sending Emails

1. Send the generated emails:
```bash
poetry run python -m email_sender.main --json_file data/content/emails.json --output_dir data/sent
```

## Environment Variables

Create a `.env` file with the following variables:
```
PERPLEXITY_API_KEY=your_perplexity_api_key
PERPLEXITY_API_URL=https://api.perplexity.ai/chat/completions
PERPLEXITY_MODEL=sonar
RESEND_API_KEY=your_resend_api_key
RESEND_API_URL=https://api.resend.com/emails
MAIL_FROM=your_sender_email
```

## Requirements

- Python 3.8 or higher
- Dependencies (automatically installed by Poetry:
  - requests
  - beautifulsoup4
  - email-validator
  - langchain
  - python-dotenv
  - pydantic
  - google-search-results
  - pytest (for development)

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