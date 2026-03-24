#create new venv
pip install -r requirements.txt

# activate 
venv/scripts/activate
conda activate eduvision

#dependencies
pip install -r requirement.txt


running
---------
.\.venv\Scripts\activate
uvicorn app.main:app --reload