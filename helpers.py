import re
from langchain.llms import OpenAI
# from langchain_community.llms import OpenAI
# from langchain import LLMChain, PromptTemplate
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from db import resume_details_collection, onboarding_details_collection
import os
import json
from firebase import Firebase
from PyPDF2 import PdfReader 
import math

firebaseConfig = {
  "apiKey": os.environ.get("FIREBASE_APIKEY"),
  "authDomain": os.environ.get("FIREBASE_AUTHDOMAIN"),
  "databaseURL": os.environ.get("FIREBASE_DATABASEURL"),
  "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
  "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
  "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
  "appId": os.environ.get("FIREBASE_APP_ID"),
  "measurementId": os.environ.get("FIREBASE_MEASUREMENT_ID")
  }


firebase = Firebase(firebaseConfig)
storage = firebase.storage()

OPENAIKEY=os.environ['OPENAIKEY']


llm = OpenAI(openai_api_key=OPENAIKEY, model_name="gpt-3.5-turbo-instruct",  max_tokens=-1)

# llm = OpenAI(openai_api_key=OPENAIKEY,  max_tokens=-1)

template = """You are a chatbot who helps people to build their resume/portfolio. This is the Markdonwn of the portfolio {html}. Analyze the Markdown properly.The following statement "{statement}" would be an instruction or information related to skills, achievements, education, projects or any other section in the resume. Analyze the statement and update the Markdown code according to statement. You are free to add or remove a section as per the scenario. Make the portfolio attractive in styling. Keep the sections of the resume one after another in vertical format. Return me only the Markdown Code.
"""

skills_analyze_template = """You are a chatbot who helps people to build their resume/portfolio. This is the text of the portfolio {html}. Analyze the text properly and find all the skills of the person from the resume and return me only the skills of the candidate in comma seperated formated.
"""
prompt = PromptTemplate(template=template, input_variables=["html", "statement"])
llm_chain = LLMChain(prompt=prompt, llm=llm)

skills_analyze_prompt = PromptTemplate(template=skills_analyze_template, input_variables=["html"])
skills_analyze_llm_chain = LLMChain(prompt=skills_analyze_prompt, llm=llm)

def query_update_billbot(user_id, statement, nxt_build_status_):
    resume_html = get_resume_html_db(user_id)
    html_code = llm_chain.run({"html": str(resume_html), "statement": statement}) 
    return html_code

def get_resume_html_db(user_id):
    if resume_data := resume_details_collection.find_one({"user_id": user_id}):
        resume_html = resume_data.get("resume_html")
        return str(resume_html)
    else:
        return ""

def add_html_to_db(user_id, html_code):
    resume_details_collection.update_one({"user_id": user_id},{"$set": {"resume_html": html_code}})

def analyze_resume(user_id, text=False):
    if not text:
        if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
            resume_html = resume_details.get("resume_html")
            skills = skills_analyze_llm_chain.run(resume_html)
            print(skills)
            skills = skills.strip()
            resume_details_collection.update_one({"user_id": user_id},{"$set": {"skills": skills}})
            return 
        else:
            return
    else:
        skills = skills_analyze_llm_chain.run(text) 
        print(skills)
        skills = skills.strip()
        resume_details_collection.update_one({"user_id": user_id},{"$set": {"skills": skills}})
        return 

def extract_text_pdf(path):
    reader = PdfReader(path) 
    print(len(reader.pages)) 
    page = reader.pages[0] 
    text = page.extract_text() 
    return text 

def upload_file_firebase(obj, path):
    storage.child(path).put(obj)
    link = storage.child(path).get_url(None)
    return link



resume_question_template = """I have asked a person whether he/she has a portfolio/resume or not.{statement} is the person's reponse. Analyse the statement and return me 'yes' if he has a resume and 'no' if he doesn't have one and if the response is something weird like not a clear cut yes or no return me 'weird'
"""

resume_question_prompt = PromptTemplate(template=resume_question_template, input_variables=["statement"])
resume_question_llm_chain = LLMChain(prompt=resume_question_prompt, llm=llm)


def query__billbot(statement):
    resp = resume_question_llm_chain.run(statement) 
    return str(resp).strip().lower()


def outbound_messages(build_status):
    messages = []
    if build_status == "introduction":
         messages = [{"user":"billbot","msg": "Hi, The right side of your screen will display your resume. You can give me instruction to build it in the chat."},{"user":"billbot","msg": "Provide a small introduction about you?"}]
    elif build_status == "contactinfo":
         messages = [{"user":"billbot","msg": "Can you provide your contact info like phone number, mail id etc.?"}]
    elif build_status == "education":
         messages = [{"user":"billbot","msg": "Tell me about your schooling and higher education?"}]
    elif build_status == "experiences":
         messages = [{"user":"billbot","msg": "Tell me about your current employment and past experiences (if any)?"}]
    elif build_status == "skills":
         messages = [{"user":"billbot","msg": "Tell me your skill list?"}]
    elif build_status == "projects":
         messages = [{"user":"billbot","msg": "Tell me about your projects?"}]
    else:
         messages = [{"user":"billbot","msg": "You can go ahead and tell me to do anything!"}]
    return messages
    

def next_build_status(build_status):
    status={
        "introduction": "contactinfo",
        "contactinfo": "education",
        "education": "experiences",
        "experiences": "skills",
        "skills": "projects",
        "projects": "endofchecklist",
        "endofchecklist": "endofchecklist"
        }
    return status.get(build_status)

def updated_build_status(user_id, nxt_build_status):
    onboarding_details_collection.update_one({"user_id": user_id},{"$set": {"build_status": nxt_build_status}})
    return 




def text_to_html(text):
  # Regular expression to match URLs, including optional http/https
  url_regex = r"(http|https):\/\/(\w+\.)+\w{2,}(?:\/\S+)?/"
  # Replace URLs with anchor tags
  return re.sub(url_regex, lambda match: f'<a href="{match.group(0)}" target="_blank">{match.group(0)}</a>', text)



def calculate_total_pages(total_elements, page_size):
    return math.ceil(total_elements / page_size)

def mbsambsasmbsa():
    html_code = llm_chain.run({"html": str(""), "statement": "I AM M b sai aditya. I am a final year student at NIT Karnataka."}) 
    return html_code