from flask import Flask, render_template, request
import os
from google import genai
import json
client = genai.Client(api_key="AIzaSyDreXjIkvh_CUti3kLxtFT0sKEGEBPcDww")

app = Flask(__name__)

# Updated some comments
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET'])
def form():
    # renders your Data Verification Form (rename it to templates/form.html)
    return render_template('form.html')

@app.route('/upload', methods=['POST'])
def upload():
    print(request.form)
    # pull values out of the submitted form
    caste_category    = request.form.get('caste-category')
    caste             = request.form.get('caste')
    has_certificate   = request.form.get('radio')       # "Yes"/"No"
    has_barcode       = request.form.get('radio1')      # "Yes"/"No"
    certificate_no    = request.form.get('caste-certificate-no')
    issuing_district  = request.form.get('issuing-district')
    application_name  = request.form.get('application-name')
    issuing_authority = request.form.get('issuing-authority')

    # handle file upload
    file = request.files.get('file')
    filename = None
    if file and file.filename:
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # simple validation: ensure required fields are filled
    required = [
        caste_category, caste, has_certificate, has_barcode,
        certificate_no, issuing_district, application_name,
        issuing_authority
    ]
    if not all(required):
        # if anything is missing, render an error
        return render_template('display.html', data={
            'error': 'Please fill out all required fields.'
        })

    myfile = client.files.upload(file=os.path.join(app.config['UPLOAD_FOLDER'], filename))

    response = client.models.generate_content(
        model="gemini-2.0-flash-thinking-exp-01-21",
        contents=[myfile, """Extract caste category, caste, issuing authority, issuing district, certificate no, application name in JSON format no need to markdown it in code block 
                Use this JSON schema:

                data = {"caste_category": str, "caste": str, "issuing_authority": str, "issuing_district": str, "certificate_no": str, "application_name": str}
                Return: data                
                """])

    # everything’s present—package it up and send to display.html
        # Parse and clean the extracted data
    try:
        print("Here is the error")
        extractedData = json.loads(response.text)
        print(extractedData)
    except Exception as e:
        print(e)
        return render_template('display.html', data={
            'error': f'Error processing extracted data: {str(e)}'
        })

    # Compare user input with extracted data (case-insensitive)
    def is_match(input_val, extracted_val):
        return input_val.strip().lower() == extracted_val.strip().lower()

    comparison = {
        'caste_category':    is_match(caste_category, extractedData.get('caste_category', '')),
        'caste':             is_match(caste, extractedData.get('caste', '')),
        'certificate_no':    is_match(certificate_no, extractedData.get('certificate_no', '')),
        'issuing_district':  is_match(issuing_district, extractedData.get('issuing_district', '')),
        'application_name':  is_match(application_name, extractedData.get('application_name', '')),
        'issuing_authority': is_match(issuing_authority, extractedData.get('issuing_authority', '')),
    }

    data = {
        'caste_category':    caste_category,
        'caste':             caste,
        'has_certificate':   has_certificate,
        'has_barcode':       has_barcode,
        'certificate_no':    certificate_no,
        'issuing_district':  issuing_district,
        'application_name':  application_name,
        'issuing_authority': issuing_authority,
        'filename':          filename,
        'gemini_response':   extractedData,
        'comparison':        comparison
    }

    return render_template('display.html', data=data, comparison=comparison)

if __name__ == '__main__':
    app.run(debug=True)
