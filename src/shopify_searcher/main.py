"""
Module to search for Shopify stores using Judge.me
"""
from typing import List, Optional
import time
from datetime import datetime
import logging
from pathlib import Path
from googlesearch import search

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

def search_shopify_stores(
    output_dir: Path,
    num_results: int = 100,
    region: str = 'es',
    lang: str = 'es',
    unique: bool = True,
    sleep_interval: int = 5, 
    save_results: bool = True
) -> List[str]:
    """
    Searches for Shopify stores that use Judge.me
    
    Args:
        output_dir: Directory to save the results
        num_results: Maximum number of results to obtain
        pause: Pause between searches to avoid blocking
        save_results: Whether to save the results to a file
    
    Returns:
        List of URLs of found stores
    """
    query = 'site:myshopify.com "powered by Judge.me"'
    logger = setup_logging(output_dir)
    stores = []
    
    logger.info(f"Starting search with query: {query}")
    logger.info(f"Searching for up to {num_results} results")
    
    try:
        for url in search(query, 
                          num_results=num_results, 
                          region=region,
                          lang=lang,
                          unique=unique, 
                          sleep_interval=sleep_interval):
            # Clean the URL to get only the domain
            domain = url.split('/')[0] + '//' + url.split('/')[2]
            # Ensure that the domain is not already in the list and is a myshopify.com URL
            if domain not in stores and 'myshopify.com' in domain:
                stores.append(domain)
                logger.info(f"Store found: {domain}")
    except Exception as e:
        logger.error(f"Error during the search: {str(e)}")
    
    logger.info(f"Search completed. Found {len(stores)} stores")
    
    if save_results and stores:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f'shopify_stores_{timestamp}.txt'
        
        with open(output_file, 'w') as f:
            for store in stores:
                f.write(f"{store}\n")
        
        logger.info(f"Results saved in: {output_file}")
    
    return stores

if __name__ == '__main__':
    output_dir = Path('data')
    output_dir.mkdir(exist_ok=True)
    stores = search_shopify_stores(output_dir)
    print(f"Found {len(stores)} stores") 