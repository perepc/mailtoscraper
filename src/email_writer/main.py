import pandas as pd
import argparse
import json
import requests
from langchain_community.llms import OpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
from pathlib import Path
from pydantic import ValidationError
from common.models.company_info import CompanyInfo
from common.models.email_data import EmailData
from common.models.shopify_store import ShopifyStore
import re
from datetime import datetime
import logging

# Load environment variables
load_dotenv()

# Perplexity API configuration
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = os.getenv('PERPLEXITY_API_URL')
PERPLEXITY_MODEL = os.getenv('PERPLEXITY_MODEL')

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
    return output_dir / f"email_generation_{timestamp}.log"

def setup_logging(log_file: Path):
    """Configure the logging system"""
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def clean_json_content(content: str) -> str:
    """Clean and extract JSON from content that might include markdown or other formatting."""
    # Remove markdown code blocks if present
    content = re.sub(r'```json\s*|\s*```', '', content)
    # Remove any leading/trailing whitespace
    content = content.strip()
    return content

def extract_and_validate_json(content: str, model_class, default_values: dict = None):
    """Extract JSON from content and validate it with the given Pydantic model."""
    try:
        # Clean the content
        cleaned_content = clean_json_content(content)
        
        # Try to parse as is first
        try:
            data = json.loads(cleaned_content)
        except json.JSONDecodeError:
            # If parsing fails, try to fix common JSON issues
            # Replace unescaped newlines in the body with \n
            cleaned_content = re.sub(r'("body":\s*"[^"]*)"([^"]*)"', 
                                   lambda m: m.group(1) + m.group(2).replace('\n', '\\n') + '"',
                                   cleaned_content, flags=re.DOTALL)
            data = json.loads(cleaned_content)
        
        # Validate with Pydantic
        return model_class.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Error processing JSON: {e}")
        print(f"Content received: {content}")
        if default_values:
            return model_class.model_validate(default_values)
        raise

# Function to generate email content using LangChain
def generate_email_content(company_info: CompanyInfo, recipient_email: str, my_company_info: CompanyInfo) -> EmailData:
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Usar un formato similar al que funciona en generate_company_info
    prompt = f"""Based on the following company information:
- Name: {company_info.name}
- URL: {company_info.url}
- Description: {company_info.description}
- Key products/services: {company_info.products_services}
- Target audience: {company_info.target_audience}

And the following information about my company:
- Name: {my_company_info.name}
- URL: {my_company_info.url}
- Description: {my_company_info.description}
- Value proposition: {my_company_info.value_proposition}

Generate a JSON with the following structure:
{{
  "email": "{recipient_email}",
  "subject": "[Concise, personalized subject line - max 50 characters]",
  "body": "[Email body content]"
}}

Guidelines for the email:
1. SUBJECT: Create a brief, curiosity-provoking subject line (30-50 characters) that mentions a specific benefit for {company_info.name}, not just my company name.

2. BODY STRUCTURE (each section MUST be wrapped in its own <p> tag):
   - First paragraph: Personalized greeting using the company name and team
   - Second paragraph: Congratulatory note about achievement + emoji
   - Third paragraph: Pain point identification and value proposition with metric
   - Fourth paragraph: Simple question to start conversation
   - Final paragraph: Signature in exact format

Example of correct paragraph structure:
<p>Hello {company_info.name} team,</p>
<p>[Congratulatory message with emoji]</p>
<p>[Pain point and value proposition]</p>
<p>[Question]</p>
<p>Best regards,<br><a href="..." style="text-decoration: none; color: #337ab7;"><strong>{my_company_info.name}</strong></a></p>

3. HTML FORMAT:
   - Every section MUST be in its own <p> tag
   - Make your company name bold using <strong> tags
   - Use <br> tag after "Best regards," in the signature
   - Include a clickable link to {my_company_info.url} with appropriate styling
   - Do not include markdown formatting in the body
   - Do not include any line breaks (\n) or additional signatures

4. TONE:
   - Conversational and direct, like writing to a colleague
   - Helpful, not salesy
   - Professional but not overly formal
   - Use an emoji in the congratulatory section (👏, 🎉, etc.)

The response should be ONLY the JSON, without any additional text, markdown formatting, or code blocks.
"""
    payload = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "model": PERPLEXITY_MODEL
    }
    
    response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Intenta extraer solo el JSON si hay texto adicional
        json_match = re.search(r'({[\s\S]*})', content)
        if json_match:
            content = json_match.group(1)
        
        try:
            # Primero intenta parsear directamente
            try:
                data = json.loads(content)
                # Si llega aquí, el JSON es válido
                email_data = EmailData.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                # Si falla, intenta una solución más drástica: reconstruir el JSON
                # Extrae los campos individuales con regex
                email_match = re.search(r'"email"\s*:\s*"([^"]*)"', content)
                subject_match = re.search(r'"subject"\s*:\s*"([^"]*)"', content)
                body_match = re.search(r'"body"\s*:\s*"([\s\S]*?)"(?=\s*[,}])', content)
                
                if email_match and subject_match and body_match:
                    email = email_match.group(1)
                    subject = subject_match.group(1)
                    body = body_match.group(1)
                    
                    email_data = EmailData(
                        email=email,
                        subject=subject,
                        body=body
                    )
                else:
                    raise ValueError("Could not extract email fields")
            
            return email_data
        except Exception as e:
            print(f"Error generating email content: {e}")
            print(f"Raw content: {content}")
            return EmailData(
                email=recipient_email,
                subject=f"ReviewSense AI for {company_info.name}",
                body=f"Dear {company_info.name} Team,\n\nWe would like to offer our ReviewSense AI services to help improve your customer reviews and feedback management.\n\nBest regards,\nReviewSense AI Team"
            )
    else:
        print(f"Error generating email content: {response.text}")
        return EmailData(
            email=recipient_email,
            subject=f"ReviewSense AI for {company_info.name}",
            body=f"Dear {company_info.name} Team,\n\nWe would like to offer our ReviewSense AI services to help improve your customer reviews and feedback management.\n\nBest regards,\nReviewSense AI Team"
        )

# Function to generate company info using Perplexity
def generate_company_info(url: str) -> CompanyInfo:
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {
                "role": "user",
                "content": f"Analyze the following website: {url}\n\nGenerate a JSON with the following structure:\n{{\n  \"name\": \"[Name of the company or store]\",\n  \"url\": \"{url}\",\n  \"description\": \"[Detailed description of the website content]\",\n  \"products_services\": \"[Key products/services offered]\",\n  \"target_audience\": \"[Target audience description]\",\n  \"value_proposition\": \"[Value proposition of the company]\"\n}}\n\nThe response should be ONLY the JSON, without additional text."
            }
        ],
        "model": "sonar"
    }
    
    response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        try:
            return extract_and_validate_json(
                content,
                CompanyInfo,
                {"name": "Unknown", "url": url, "description": "Could not generate company description."}
            )
        except Exception as e:
            print(f"Error generating company info: {e}")
            return CompanyInfo(
                name="Unknown",
                url=url,
                description="Could not generate company description."
            )
    else:
        print(f"Error generating company info: {response.text}")
        return CompanyInfo(
            name="Unknown",
            url=url,
            description="Could not generate company description."
        )

# Main function
def main(json_file: Path, output_dir: Path, my_company_url: str):
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    log_file = get_log_filename(output_dir)
    setup_logging(log_file)
    
    print(f"Reading JSON file: {json_file}")
    print(f"Results will be saved to: {output_dir.absolute()}")
    print(f"- Generation log: {log_file.name}")
    
    # Read the JSON file
    with open(json_file, 'r') as f:
        shopify_stores = json.load(f)
    
    # Convert dictionaries to ShopifyStore objects
    shopify_stores = [ShopifyStore(**data) for data in shopify_stores]
    
    # List to store results
    results = []
    
    logging.info(f"Starting email content generation process")
    logging.info(f"My company URL: {my_company_url}")
    logging.info("-" * 80)

    my_company_info = generate_company_info(my_company_url)
    logging.info(f"My company information generated:")
    logging.info(f"  Name: {my_company_info.name}")
    logging.info(f"  Description: {my_company_info.description}")
    logging.info("-" * 80)

    # save my company info to a file with the company name create companies folder if it doesn't exist
    companies_dir = output_dir / "companies"
    if not companies_dir.exists():
        companies_dir.mkdir(parents=True, exist_ok=True)
    with open(companies_dir / f"{my_company_info.name}.json", "w") as f:
        json.dump(my_company_info.model_dump(), f, indent=2, ensure_ascii=False)

    # Iterate over DataFrame rows
    total_rows = len(shopify_stores)
    successful_generations = 0
    failed_generations = 0

    for index, shopify_store in enumerate(shopify_stores):
        url = shopify_store.custom_domain
        email = shopify_store.email
        
        logging.info(f"\nProcessing email {index + 1} of {total_rows}")
        logging.info(f"URL: {url}")
        logging.info(f"Email: {email}")
        
        try:
            # Generate company info
            company_info = generate_company_info(url)
            logging.info(f"Company information generated:")
            logging.info(f"  Name: {company_info.name}")
            logging.info(f"  Description: {company_info.description}")

            # save company info to a file with the company name 
            with open(companies_dir / f"{company_info.name}.json", "w") as f:
                json.dump(company_info.model_dump(), f, indent=2, ensure_ascii=False)
            
            # Generate email content using company info
            email_data = generate_email_content(company_info, email, my_company_info)
            result = email_data.model_dump()
            result['status'] = 'ready'
            
            successful_generations += 1
            results.append(result)
            logging.info(f"✓ Email content generated successfully for: {email}")
            
        except Exception as e:
            logging.error(f"Error generating content for {url}: {str(e)}")
            failed_generations += 1
            results.append({
                'email': email,
                'url': url,
                'status': 'error',
                'error': str(e)
            })
        
        logging.info("-" * 80)
    
    # Save all results to a JSON file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'generated_emails_{timestamp}.json'
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Log final summary
    logging.info("\nFinal summary:")
    logging.info(f"Total emails processed: {total_rows}")
    logging.info(f"Emails generated successfully: {successful_generations}")
    logging.info(f"Failed generations: {failed_generations}")
    logging.info(f"Results saved to: {output_file}")
    
    print(f"\nProcess completed:")
    print(f"- {successful_generations} emails generated successfully")
    print(f"- {failed_generations} failed generations")
    print(f"- Results saved to '{output_file}'")
    print(f"- Activity log in '{log_file}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate personalized email content based on web content.')
    parser.add_argument('--my_company', type=str, help='URL of my company', required=True)
    parser.add_argument('--json_file', type=Path, help='Path to the input JSON file', required=True)
    parser.add_argument('--output_dir', type=Path, help='Directory where output files will be saved', required=True)
    
    args = parser.parse_args()
    main(args.json_file, args.output_dir, args.my_company)
