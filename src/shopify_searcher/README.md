## Setting Up Google Cloud Project and Download Credentials

First, you need to set up a project in Google Cloud and enable the Search Console API:

1. Go to Google Cloud Console
2. Create a new project (or select an existing one)
3. Search for and enable the "Search Console API"
4. Create OAuth 2.0 credentials:
   - Go to "Credentials" → "Create credentials" → "OAuth client ID"
   - Configure the consent screen (type "External")
   - Select "Desktop app" as the application type
   - Download the JSON credentials file

## Setting Up Custom Search Engine

You need to create a Custom Search Engine:

1. Go to Programmable Search Engine
2. Create a new search engine
3. In the settings, check "Search the entire web"
4. Copy the search engine ID (appears as "cx") and replace it in the code

