import re
import logging
from typing import List, Tuple, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
import sys
from pathlib import Path
import argparse
from datetime import datetime
from email_validator import validate_email, EmailNotValidError
import json
from common.models.shopify_store import ShopifyStore

def get_timestamp() -> str:
    """
    Get current timestamp in a format suitable for filenames
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def get_output_filenames(output_dir: Path) -> Tuple[Path, Path]:
    """
    Generate timestamped filenames for output files
    Returns a tuple of (emails_file, log_file)
    """
    timestamp = get_timestamp()
    emails_file = output_dir / f"found_emails_{timestamp}.json"
    log_file = output_dir / f"scraping_results_{timestamp}.log"
    return emails_file, log_file

def setup_logging(log_file: Path):
    """Configure the logging system"""
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def clean_email(email: str) -> str:
    """
    Clean an email address by:
    - Removing URL encoding (%20, etc.)
    - Removing whitespace
    - Removing common escape characters
    """
    # Decode URL encoding
    email = unquote(email)
    # Remove whitespace
    email = email.strip()
    # Remove escape characters
    email = email.replace('\\n', '').replace('\\r', '').replace('\\t', '')
    return email

def has_text_prefix(text: str) -> bool:
    """
    Check if there's text attached to the beginning of what should be an email
    Returns True if there's text prefix (invalid), False otherwise (valid)
    """
    # Look for any letter or number before the @ that's not part of a valid email
    match = re.match(r'^.*?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})$', text)
    if match:
        prefix = text[:text.index(match.group(1))]
        # If there's any text before the actual email, it's invalid
        return bool(prefix.strip())
    return True

def has_text_suffix(text: str) -> bool:
    """
    Check if there's text attached to the end of what should be an email
    Returns True if there's text suffix (invalid), False otherwise (valid)
    """
    # Find the email pattern and check if there's any text after it
    match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(.+)$', text)
    if match:
        suffix = match.group(2)
        # Si hay cualquier carácter que no sea espacio después del email, es inválido
        return bool(suffix.strip())
    return False

def extract_clean_email(text: str) -> str:
    """
    Extract a clean email from text, removing any attached text
    Returns None if no valid email is found
    """
    # Search for the basic email pattern
    email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    match = re.search(email_pattern, text)
    if match:
        return clean_email(match.group(1))
    return None

def is_valid_domain_extension(domain: str) -> bool:
    """
    Check if the domain has a valid top-level extension
    """
    # Lista común de TLDs válidos
    valid_tlds = {
        'com', 'org', 'net', 'edu', 'gov', 'mil', 'int',
        'es', 'eu', 'uk', 'de', 'fr', 'it', 'pt', 'nl',
        'info', 'biz', 'io', 'co', 'me', 'tv', 'app',
        'dev', 'cloud', 'online', 'store', 'shop', 'tech',
        'cat', 'pro', 'xyz', 'site', 'web', 'blog'
    }
    
    try:
        # Get the extension (last component of the domain)
        extension = domain.split('.')[-1].lower()
        return extension in valid_tlds
    except:
        return False

def validate_email_address(email: str) -> bool:
    """
    Validate email using email_validator library
    Returns True if email is valid, False otherwise
    """
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False

def clean_domain(email: str) -> str:
    """
    Clean the domain part of an email by removing invalid characters from the end
    Returns the cleaned email or None if no valid domain is found
    """
    # Separate the email into username and domain
    try:
        username, domain = email.split('@')
    except ValueError:
        return None
    
    # If there's no dot in the domain, it's invalid
    if '.' not in domain:
        return None
    
    # Remove characters from the end of the domain until a valid one is found
    original_domain = domain
    while domain:
        # Check if the current domain has a valid format
        if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
            # Check if the domain extension is valid
            if is_valid_domain_extension(domain):
                if domain != original_domain:
                    logging.info(f"    ℹ Domain cleaned: {original_domain} -> {domain}")
                return f"{username}@{domain}"
            else:
                logging.info(f"    ℹ Invalid domain extension: {domain}")
        
        # Remove one character from the end
        domain = domain[:-1]
        # If after removing one character there's no dot, the domain is invalid
        if '.' not in domain:
            return None
    
    return None

def is_valid_email(email: str) -> bool:
    """
    Validate if an email address has a valid format
    Checks that the domain part follows standard rules
    """
    # Clean the email first
    email = clean_email(email)
    
    # Try to clean the domain if necessary
    cleaned_email = clean_domain(email)
    if not cleaned_email:
        return False
    
    # Regular expression for validating email with strict domain format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, cleaned_email))

def is_email_contained_in_another(email: str, email_list: List[str]) -> bool:
    """
    Check if this email contains any other email in the list
    Returns True if this email contains a shorter email (should be discarded)
    Returns False if this email should be kept
    """
    email_clean = email.lower()
    for other in email_list:
        other_clean = other.lower()
        # If the other email is shorter and is contained in this email
        if len(other_clean) < len(email_clean) and other_clean in email_clean:
            logging.info(f"    ✗ Discarded (contains {other}): {email}")
            return True
    return False

def extract_emails_from_text(text: str) -> List[str]:
    """
    Extract email addresses from text using regular expressions
    Only returns valid email addresses
    """
    # First, find all possible emails with context
    email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z0-9._%+-]+)'
    potential_matches = re.finditer(email_pattern, text)
    
    # First pass: collect all valid emails
    valid_emails = []
    seen_emails = set()  # To avoid duplicates in logging
    
    for match in potential_matches:
        email = clean_email(match.group(1))
        cleaned_email = clean_domain(email)
        
        if cleaned_email and cleaned_email not in seen_emails:
            seen_emails.add(cleaned_email)
            if is_valid_email(cleaned_email):
                if not validate_email_address(cleaned_email):
                    logging.info(f"    ✗ Discarded (invalid email format): {cleaned_email}")
                    continue
                    
                if cleaned_email != email:
                    logging.info(f"    ✓ Cleaned and accepted: {email} -> {cleaned_email}")
                else:
                    logging.info(f"    ✓ Found: {cleaned_email}")
                valid_emails.append(cleaned_email)
            else:
                logging.info(f"    ✗ Discarded (invalid format): {email}")
    
    # Second pass: filter emails that contain others
    filtered_emails = []
    # Process the longest emails first to see if they contain others
    for email in sorted(valid_emails, key=len, reverse=True):
        if not is_email_contained_in_another(email, valid_emails):
            logging.info(f"    ✓ Accepted: {email}")
            filtered_emails.append(email)
    
    return filtered_emails

def read_urls_from_file(filepath: str) -> List[str]:
    """
    Read URLs from a text file, one URL per line
    Ignores empty lines and lines starting with #
    """
    try:
        with open(filepath, 'r') as f:
            # Read lines, strip whitespace, and filter out empty lines and comments
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        return urls
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)

def scrape_emails_from_url(url: str) -> Tuple[List[str], bool]:
    """
    Extract emails from a given URL
    Returns a tuple with the list of emails and a boolean indicating if emails were found
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        logging.info("Analyzing visible text:")
        # Search in visible text
        visible_text = soup.get_text()
        emails = extract_emails_from_text(visible_text)
        
        logging.info("Analyzing mailto links:")
        # Search in mailto: links
        mailto_links = soup.select('a[href^="mailto:"]')
        mailto_emails = []
        for link in mailto_links:
            href = link.get('href', '')
            if '@' in href:
                email = href.replace('mailto:', '').strip()
                email = clean_email(email)
                if is_valid_email(email) and validate_email_address(email):
                    logging.info(f"    ✓ Found in mailto: {email}")
                    mailto_emails.append(email)
                else:
                    logging.info(f"    ✗ Discarded from mailto (invalid format): {email}")
        
        # Add mailto emails
        emails.extend(mailto_emails)
        
        # Clean and deduplicate emails
        unique_emails = []
        # Process the longest emails first
        for email in sorted(set(emails), key=len, reverse=True):
            if not is_email_contained_in_another(email, emails):
                unique_emails.append(email)
        
        return unique_emails, bool(unique_emails)
    
    except Exception as e:
        logging.error(f"Error processing {url}: {str(e)}")
        return [], False

def process_store(store: ShopifyStore, log_file: Path) -> ShopifyStore:
    """
    Process a single ShopifyStore and extract email
    Returns updated ShopifyStore with email field populated if found
    """
    setup_logging(log_file)
    
    logging.info(f"\nProcessing store: {store.custom_domain}")
    emails, found = scrape_emails_from_url("https://" + store.custom_domain)
    
    if found and emails:
        store.email = emails[0]  # Tomamos el primer email encontrado
        logging.info(f"✓ Found email: {store.email}")
    else:
        logging.info(f"✗ No valid email found for {store.custom_domain}")
    
    logging.info("-" * 80)
    return store

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Extract email addresses from Shopify stores.')
    parser.add_argument('--input_file', help='JSON file containing ShopifyStore objects', type=Path, required=True)
    parser.add_argument('-o', '--output-dir', 
                       help='Directory where output files will be saved (default: current directory)',
                       default='.')
    return parser.parse_args()

def main():
    """
    Main project function
    """
    args = parse_arguments()
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped filenames
    output_file, log_file = get_output_filenames(output_dir)
    
    print(f"Reading stores from: {args.input_file}")
    
    # Read stores from JSON file
    try:
        with open(args.input_file, 'r') as f:
            stores_data = json.load(f)
            stores = [ShopifyStore(**store) for store in stores_data]
    except Exception as e:
        print(f"Error reading input file: {str(e)}")
        sys.exit(1)
    
    if not stores:
        print("No stores found in the input file")
        sys.exit(1)
    
    print(f"Found {len(stores)} stores to process")
    print(f"Output files will be saved in: {output_dir.absolute()}")
    print(f"- Results will be saved to: {output_file.name}")
    print(f"- Log will be saved to: {log_file.name}")
    print("Starting email extraction...")
    
    # Process each store
    processed_stores = [process_store(store, log_file) for store in stores]
    
    # Save the processed stores to JSON file
    with open(output_file, 'w') as f:
        json.dump([store.model_dump() for store in processed_stores if store.email], f, indent=4)
    
    emails_found = sum(1 for store in processed_stores if store.email)
    print(f"\nProcess completed:")
    print(f"- Found emails for {emails_found} out of {len(stores)} stores")
    print(f"- Results have been saved to '{output_file}'")
    print(f"- Activity log is in '{log_file}'")

if __name__ == "__main__":
    main() 