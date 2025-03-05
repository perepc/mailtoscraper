import requests
from dotenv import load_dotenv
import os
from pydantic import BaseModel
import argparse
from pathlib import Path
import json
import logging
from datetime import datetime
from common.models.email_data import EmailData
# Load environment variables
load_dotenv()

# Resend API configuration
RESEND_API_KEY = os.getenv('RESEND_API_KEY')
RESEND_API_URL = os.getenv('RESEND_API_URL')
MAIL_FROM = os.getenv('MAIL_FROM')

def get_timestamp() -> str:
    """
    Get current timestamp in a format suitable for filenames
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def get_log_filename(output_dir: Path) -> Path:
    """
    Generate timestamped filename for log file
    """
    timestamp = get_timestamp()
    return output_dir / f"email_sending_results_{timestamp}.log"

def setup_logging(log_file: Path):
    """Configure the logging system"""
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# Function to send email using Resend
def send_email(email_data: EmailData):
    data = {
        "from": MAIL_FROM,
        "to": email_data.email,
        "subject": email_data.subject,
        "html": email_data.body
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(RESEND_API_URL, json=data, headers=headers)
        response.raise_for_status()
        
        logging.info(f"✓ Email successfully sent to: {email_data.email}")
        logging.info(f"  Subject: {email_data.subject}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Error sending email to {email_data.email}: {str(e)}")
        return False
    finally:
        logging.info("-" * 80)  # Visual separator in log

def main(json_file: Path, output_dir: Path):
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    log_file = get_log_filename(output_dir)
    setup_logging(log_file)
    
    print(f"Sending results will be saved to: {log_file}")
    
    # Read the JSON file
    with open(json_file, 'r') as f:
        emails_to_send = json.load(f)
    
    # Initialize counters
    total_emails = len(emails_to_send)
    successful_sends = 0
    failed_sends = 0
    
    logging.info(f"Starting email sending process")
    logging.info(f"Total emails to send: {total_emails}")
    logging.info("-" * 80)
    
    # Process each email
    for index, email_data_dict in enumerate(emails_to_send, 1):
        try:
            # Skip emails that had generation errors
            if email_data_dict.get('status') == 'error':
                logging.warning(f"Skipping email {index} due to generation error: {email_data_dict.get('error', 'Unknown error')}")
                failed_sends += 1
                continue
            
            # Convert dictionary to EmailData object
            email_data = EmailData(
                email=email_data_dict['email'],
                subject=email_data_dict['subject'],
                body=email_data_dict['body']
            )
            
            logging.info(f"\nProcessing email {index} of {total_emails}")
            logging.info(f"Recipient: {email_data.email}")
            
            # Send the email
            if send_email(email_data):
                successful_sends += 1
            else:
                failed_sends += 1
                
        except Exception as e:
            logging.error(f"Error processing email {index}: {str(e)}")
            failed_sends += 1
    
    # Log final summary
    logging.info("\nFinal summary:")
    logging.info(f"Total emails processed: {total_emails}")
    logging.info(f"Emails sent successfully: {successful_sends}")
    logging.info(f"Failed sends: {failed_sends}")
    
    print(f"\nProcess completed:")
    print(f"- {successful_sends} emails sent successfully")
    print(f"- {failed_sends} failed sends")
    print(f"- Activity log in '{log_file}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Send emails using Resend API.')
    parser.add_argument('--json_file', type=Path, help='Path to the input JSON file', required=True)
    parser.add_argument('--output_dir', type=Path, help='Directory where log files will be saved', required=True)
    args = parser.parse_args()
    
    main(args.json_file, args.output_dir)
