import os
import pymongo

ENVIRONMENT = os.environ["ENVIRONMENT"]
if ENVIRONMENT == "local":
    connection_string = "mongodb://localhost:27017"
    DB_NAME = "jobsaathi-prod"
else:    
    MONGO_CLUSTER = os.environ["MONGO_URI"]
    MONGO_USERNAME = os.environ["MONGO_USERNAME"]
    MONGO_PASSWORD = os.environ["MONGO_PASSWORD"]
    DB_NAME = os.environ["DB_NAME"]
    connection_string = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_CLUSTER}/?retryWrites=true&ssl=true&ssl_cert_reqs=CERT_NONE&w=majority"


db_client = pymongo.MongoClient(connection_string)
db_client = db_client.get_database(DB_NAME)

user_details_collection = db_client['user_details']
resume_details_collection = db_client['resume']
onboarding_details_collection = db_client['onboarding_details']
jobs_details_collection = db_client['jobs_details']
saved_jobs_collection = db_client['saved_jobs']
candidate_job_application_collection = db_client['candidate_job_application']
chatbot_collection = db_client['chatbot']
profile_details_collection = db_client['profile_details']
chat_details_collection = db_client['chat_details']
connection_details_collection = db_client['connection_details']

