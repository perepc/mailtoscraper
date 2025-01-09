import re
import logging
from typing import List, Tuple
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import sys
from pathlib import Path
import argparse
from datetime import datetime
from email_validator import validate_email, EmailNotValidError

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
    emails_file = output_dir / f"found_emails_{timestamp}.txt"
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
    # Buscar el patrón de email básico
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
        # Obtener la extensión (último componente del dominio)
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
    # Separar el email en usuario y dominio
    try:
        username, domain = email.split('@')
    except ValueError:
        return None
    
    # Si no hay punto en el dominio, no es válido
    if '.' not in domain:
        return None
    
    # Ir quitando caracteres del final del dominio hasta encontrar uno válido
    original_domain = domain
    while domain:
        # Verificar si el dominio actual tiene un formato válido
        if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
            # Verificar si la extensión del dominio es válida
            if is_valid_domain_extension(domain):
                if domain != original_domain:
                    logging.info(f"    ℹ Domain cleaned: {original_domain} -> {domain}")
                return f"{username}@{domain}"
            else:
                logging.info(f"    ℹ Invalid domain extension: {domain}")
        
        # Quitar un carácter del final
        domain = domain[:-1]
        # Si después de quitar un carácter no hay punto, el dominio no es válido
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
        # Si el otro email es más corto y está contenido en este email
        if len(other_clean) < len(email_clean) and other_clean in email_clean:
            logging.info(f"    ✗ Discarded (contains {other}): {email}")
            return True
    return False

def extract_emails_from_text(text: str) -> List[str]:
    """
    Extract email addresses from text using regular expressions
    Only returns valid email addresses
    """
    # Primero, encontrar todos los posibles emails con contexto
    email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z0-9._%+-]+)'
    potential_matches = re.finditer(email_pattern, text)
    
    # Primera pasada: recolectar todos los emails válidos
    valid_emails = []
    seen_emails = set()  # Para evitar duplicados en el logging
    
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
    
    # Segunda pasada: filtrar emails que contienen a otros
    filtered_emails = []
    # Procesar primero los emails más largos para ver si contienen a otros
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
        
        # Añadir emails de mailto
        emails.extend(mailto_emails)
        
        # Clean and deduplicate emails
        unique_emails = []
        # Procesar primero los emails más largos
        for email in sorted(set(emails), key=len, reverse=True):
            if not is_email_contained_in_another(email, emails):
                unique_emails.append(email)
        
        return unique_emails, bool(unique_emails)
    
    except Exception as e:
        logging.error(f"Error processing {url}: {str(e)}")
        return [], False

def process_urls(urls: List[str], log_file: Path) -> List[str]:
    """
    Process a list of URLs and extract all found emails
    """
    setup_logging(log_file)
    all_emails = set()
    
    for url in urls:
        logging.info(f"\nProcessing URL: {url}")
        emails, found = scrape_emails_from_url(url)
        
        if found:
            all_emails.update(emails)
            logging.info(f"✓ Found {len(emails)} valid emails in {url}")
            logging.info("Summary of valid emails found:")
            for email in emails:
                logging.info(f"  ✓ {email}")
        else:
            logging.info(f"✗ No valid emails found in {url}")
        
        logging.info("-" * 80)  # Visual separator in log
    
    return list(all_emails)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Extract email addresses from a list of websites.')
    parser.add_argument('urls_file', help='Text file containing URLs to process (one per line)')
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
    emails_file, log_file = get_output_filenames(output_dir)
    
    print(f"Reading URLs from: {args.urls_file}")
    
    # Read URLs from file
    urls = read_urls_from_file(args.urls_file)
    if not urls:
        print("No URLs found in the input file")
        sys.exit(1)
    
    print(f"Found {len(urls)} URLs to process")
    print(f"Output files will be saved in: {output_dir.absolute()}")
    print(f"- Emails will be saved to: {emails_file.name}")
    print(f"- Log will be saved to: {log_file.name}")
    print("Starting email extraction...")
    
    emails = process_urls(urls, log_file)
    
    # Save found emails to a file
    with open(emails_file, 'w') as f:
        for email in sorted(emails):
            f.write(f"{email}\n")
    
    print(f"\nProcess completed:")
    print(f"- {len(emails)} unique emails have been found")
    print(f"- Results have been saved to '{emails_file}'")
    print(f"- Activity log is in '{log_file}'")

if __name__ == "__main__":
    main() 