"""
Module to search for Shopify stores using Judge.me
"""
from typing import List, Optional, Tuple
from datetime import datetime
import logging
from pathlib import Path
import argparse
from pydantic import BaseModel
import requests
import json
from requests.exceptions import RequestException
from time import sleep
import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from common.models.shopify_store import ShopifyStore

# Configuración para Google Search API
SCOPES = ['https://www.googleapis.com/auth/cse'] 
CREDENTIALS_FILE = 'client_secret.json'
TOKEN_PICKLE_FILE = 'token.pickle'

def get_credentials():
    """Obtiene o refresca las credenciales OAuth2."""
    creds = None
    
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def setup_logging(output_dir: Path) -> logging.Logger:
    """Configures logging for the search module"""
    logger = logging.getLogger('shopify_searcher')
    logger.setLevel(logging.INFO)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = output_dir / f'shopify_search_{timestamp}.log'
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

def search_with_retry(func):
    """
    Decorator that implements exponential backoff retries
    """
    def wrapper(*args, **kwargs):
        max_retries = 3
        initial_delay = 2
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                delay = initial_delay * (2 ** attempt) + uniform(0, 1)
                logger = logging.getLogger('shopify_searcher')
                logger.warning(f"Attempt {attempt + 1} failed. Waiting {delay:.2f} seconds. Error: {str(e)}")
                sleep(delay)
        return None
    return wrapper

@search_with_retry
def get_custom_domain_redirect(url_shopify: str) -> Tuple[Optional[str], str]:
    try:
        # Configure the User-Agent to simulate a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Perform the request following redirects
        response = requests.get(url_shopify, headers=headers, allow_redirects=True)
        
        # Get the final URL after redirects
        url_final = response.url
        
        # Check if there was a redirect to a different domain
        if url_shopify != url_final:
            return url_final, "A custom domain was found"
        else:
            return url_shopify, "No custom domain redirect was found"
            
    except Exception as e:
        return None, f"Error following redirects: {str(e)}"

def search_shopify_stores(
    output_dir: Path,
    num_results: int = 100,
    region: str = 'es',
    lang: str = 'es',
    save_results: bool = True,
    exceptions_file: Optional[Path] = None,
    custom_search_engine_id: str = None
) -> List[ShopifyStore]:
    """
    Searches for Shopify stores that use Judge.me using Google Custom Search API
    """
    logger = setup_logging(output_dir)
    stores = []
    processed_domains = set()  # Set to track processed domains
    
    # Load exceptions and build query
    exceptions = set()
    query = 'site:myshopify.com "powered by Judge.me"'
    
    if exceptions_file and exceptions_file.exists():
        with open(exceptions_file, 'r') as f:
            exceptions = set(line.strip() for line in f)
            # Add -site: operator for each exception
            exclude_sites = ' '.join(f'-site:{domain}' for domain in exceptions)
            query = f'{query} {exclude_sites}'
    
    logger.info(f"Starting search with query: {query}")
    logger.info(f"Searching for up to {num_results} results")
    
    try:
        # Obtain credentials and build the service
        creds = get_credentials()
        service = build('customsearch', 'v1', credentials=creds)
        
        # Calculate number of iterations needed (10 results per request)
        iterations = (num_results + 9) // 10
        
        for i in range(iterations):
            start_index = (i * 10) + 1  # Google's API uses 1-based indexing
            
            logger.info(f"Fetching results {start_index} to {start_index + 9}")
            
            result = service.cse().list(
                q=query,
                cx=custom_search_engine_id,
                start=start_index,
                num=10  # Maximum allowed by the API
            ).execute()
            
            if 'items' not in result:
                logger.info("No more results available")
                break
                
            for item in result['items']:
                url = item['link']
                # Clean the URL to get only the domain
                domain = url.split('/')[0] + '//' + url.split('/')[2]
                
                # Skip if we've already processed this domain
                if domain in processed_domains:
                    logger.info(f"Skipping duplicate domain: {domain}")
                    continue
                
                if 'myshopify.com' in domain:
                    custom_domain, reason = get_custom_domain_redirect(domain)
                    logger.info(f"Custom domain redirect: {custom_domain} - {reason}")
                    
                    # Skip if we've already processed this custom domain
                    if custom_domain and custom_domain in processed_domains:
                        logger.info(f"Skipping duplicate custom domain: {custom_domain}")
                        continue
                    
                    if custom_domain:
                        shopify_store = ShopifyStore(custom_domain=custom_domain, shopify_url=domain, region=region, lang=lang)
                        processed_domains.add(custom_domain)
                    else:
                        shopify_store = ShopifyStore(custom_domain=domain, shopify_url=domain, region=region, lang=lang)
                        processed_domains.add(domain)
                    
                    stores.append(shopify_store)
                    logger.info(f"Store found: {shopify_store.custom_domain} - {shopify_store.shopify_url}")
                    
                    if len(stores) >= num_results:
                        break
            
            if len(stores) >= num_results:
                break
                    
    except HttpError as error:
        logger.error(f"Error during the search: {error}")
                
    except Exception as e:
        logger.error(f"Error during the search: {str(e)}")
    
    logger.info(f"Search completed. Found {len(stores)} unique stores")
    
    if save_results and stores:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f'shopify_stores_{timestamp}.json'
        
        with open(output_file, 'w') as f:
            json.dump([store.model_dump() for store in stores], f, indent=4)
        
        logger.info(f"Results saved in: {output_file}")
    
    return stores

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Search for Shopify stores using Judge.me')
    parser.add_argument('--exceptions_file', type=Path, help='Exceptions file (optional)')
    # parser.add_argument('--num_results', type=int, default=100, help='Number of results to return (default=100)')
    parser.add_argument('--region', type=str, required=True, help='Region')
    parser.add_argument('--lang', type=str, required=True, help='Language')
    parser.add_argument('--output_dir', type=Path, default=Path('.'), help='Output directory (default=current directory)')
    parser.add_argument('--custom_search_engine_id', type=str, required=True, help='Google Custom Search Engine ID')

    args = parser.parse_args()

    stores = search_shopify_stores(
        output_dir=args.output_dir,
        # num_results=args.num_results,
        region=args.region,
        lang=args.lang,
        exceptions_file=args.exceptions_file,
        custom_search_engine_id=args.custom_search_engine_id
    )
    print(f"Found {len(stores)} stores") 