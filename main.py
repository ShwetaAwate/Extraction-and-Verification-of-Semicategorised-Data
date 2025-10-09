import PyPDF2

with open ('Unit_I_PE_IOT.pdf', 'rb') as file:
  reader = PyPDF2.PdfReader(file)

  for page in reader.pages:
    text = page.extract_text()
    print(text)
    
