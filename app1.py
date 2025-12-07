from flask import Flask, render_template, request
import os
from google import genai
import json
import time

# --- CHOOSE YOUR CLIENT ---
# Option 1: Use the MockClient (for testing without an API key)
# class MockFile: ... (etc.)
# client = MockClient(api_key="YOUR_API_KEY_HERE")

# Option 2: Use the REAL Gemini Client
# Remember to run: pip install google-generativeai
client = genai.Client(api_key="AIzaSyDreXjIkvh_CUti3kLxtFT0sKEGEBPcDww") 
# ---

app = Flask(__name__, template_folder='templates') 

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Load the "Source of Truth" database
try:
    with open('master_database.json', 'r') as f:
        MASTER_DATABASE = json.load(f)
except FileNotFoundError:
    print("CRITICAL ERROR: master_database.json not found.")
    MASTER_DATABASE = {}
except json.JSONDecodeError:
    print("CRITICAL ERROR: master_database.json is not valid JSON.")
    MASTER_DATABASE = {}

@app.route('/', methods=['GET'])
def form():
    # Renders the form1.html from your 'templates' folder
    return render_template('form1.html')

@app.route('/upload', methods=['POST'])
def upload():
    # 1. --- Get User Input (Source A: Form) ---
    form_data = {
        'caste_category':    request.form.get('caste-category'),
        'caste':             request.form.get('caste'),
        'certificate_no':    request.form.get('caste-certificate-no'),
        'issuing_district':  request.form.get('issuing-district'),
        'application_name':  request.form.get('application-name')
        # 'issuing_authority' has been removed
    }

    # Handle file upload
    file = request.files.get('file')
    if not (file and file.filename):
        return render_template('display1.html', 
                               error='No file uploaded. Please select a file to upload.')

    filename = file.filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # 2. --- Get Extracted Data (Source B: Document) ---
    try:
        myfile = client.files.upload(file=file_path)
    except Exception as e:
        print(f"Error during file upload: {e}")
        return render_template('display1.html', error=f'Error uploading file: {str(e)}')

    extracted_data = None
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            print(f"Attempt {attempt + 1} of {MAX_RETRIES} to generate content...")
            
            # --- UPDATED PROMPT ---
            response = client.models.generate_content(
                model="gemini-2.0-flash-thinking-exp-01-21", # Use your actual model
                contents=[myfile, """Extract caste category, caste, issuing district, certificate no, application name in JSON format no need to markdown it in code block 
                        Use this JSON schema:
                        data = {"caste_category": str, "caste": str, "issuing_district": str, "certificate_no": str, "application_name": str}
                        Return: data                
                        """])
            
            extracted_data = json.loads(response.text)
            print("Successfully parsed JSON.")
            break 
            
        except json.JSONDecodeError:
            print(f"Attempt {attempt + 1} failed: Invalid JSON received from API.")
            print(f"Response text: {response.text}")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with API error: {e}")
        
        if attempt < MAX_RETRIES - 1:
            time.sleep(1)

    if extracted_data is None:
        print("All attempts to get valid JSON failed.")
        return render_template('display1.html', 
                               error='Error processing document: Could not get a valid response from the AI model after several attempts.')

    try:
        for key, value in extracted_data.items():
            if isinstance(value, str):
                extracted_data[key] = value.strip()
            elif key in ['caste_category', 'caste', 'issuing_district', 'certificate_no', 'application_name']:
                 extracted_data[key] = "" # Ensure our main keys exist
    except AttributeError:
        print(f"Error: Extracted data was valid JSON but not a dictionary. Data: {extracted_data}")
        return render_template('display1.html', 
                               error='Error processing document: The AI model returned an unexpected data format.')


    # 3. --- Get Official Data (Source C: Database) ---
    lookup_cert_no = extracted_data.get('certificate_no')
    if not lookup_cert_no:
        return render_template('display1.html', 
                               error='Could not extract a Certificate Number from the document.',
                               form_data=form_data,
                               extracted_data=extracted_data)

    master_record = MASTER_DATABASE.get(lookup_cert_no)
    
    # 4. --- COMBINED 3-WAY VERIFICATION LOGIC ---
    
    def is_match(val1, val2):
        if not isinstance(val1, str) or not isinstance(val2, str):
            return False
        return val1.strip().lower() == val2.strip().lower()
        
    # --- UPDATED FIELDS TO CHECK ---
    fields_to_check = ['caste_category', 'caste', 'issuing_district', 'application_name']

    # This single object will hold the entire result
    verification_result = {
        'overall_status': 'PENDING',
        'message': '',
        'check_A_vs_B': {}, # Holds Form vs. Document check
        'check_B_vs_C': {}  # Holds Document vs. Database check
    }

    # Step A: Check if record exists (C)
    if not master_record:
        verification_result['overall_status'] = 'FAILED'
        verification_result['message'] = 'Verification Failed: The certificate number from your document does not exist in the official records.'
        return render_template('display1.html',
                               form_data=form_data,
                               extracted_data=extracted_data,
                               verification_result=verification_result)

    # Step B: Perform Document vs. Database check (B vs C)
    is_forged = False
    for field in fields_to_check:
        extracted_val = extracted_data.get(field, '')
        master_val = master_record.get(field, '')
        if is_match(extracted_val, master_val):
            verification_result['check_B_vs_C'][field] = 'VERIFIED'
        else:
            verification_result['check_B_vs_C'][field] = 'MISMATCH'
            is_forged = True

    # Step C: Perform Form vs. Document check (A vs B)
    input_mismatch = False
    for field in fields_to_check:
        form_val = form_data.get(field, '')
        extracted_val = extracted_data.get(field, '')
        if is_match(form_val, extracted_val):
            verification_result['check_A_vs_B'][field] = 'MATCH'
        else:
            verification_result['check_A_vs_B'][field] = 'MISMATCH'
            input_mismatch = True

    # Step D: Determine the single, final verdict
    if is_forged:
        verification_result['overall_status'] = 'FORGERY DETECTED'
        verification_result['message'] = 'Verification Failed: The uploaded document is fraudulent. Its data does not match official records.'
    elif input_mismatch:
        verification_result['overall_status'] = 'INPUT MISMATCH'
        verification_result['message'] = 'Verification Failed: The data you entered in the form does not match the data on the document.'
    else:
        # Only if B==C AND A==B
        verification_result['overall_status'] = 'VERIFIED'
        verification_result['message'] = 'Verified: Form data, document data, and official records all match.'


    # 6. --- Render the template with the single verification result ---
    return render_template('display1.html', 
                           form_data=form_data,
                           extracted_data=extracted_data,
                           master_record=master_record,
                           verification_result=verification_result) # Pass the single object

if __name__ == '__main__':
    app.run(debug=True)