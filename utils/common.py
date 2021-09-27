import json
import cloudinary
from cloudinary import uploader

# def upload_to_s3(key, data, complete_file=False):
#     session = Session(aws_access_key_id=keysInformation['aws.accessKey'],
#                       aws_secret_access_key=keysInformation['aws.secretKey'],
#                       region_name=keysInformation["s3.region"]).resource('s3').Bucket(keysInformation["s3.bucket"])
#     if complete_file:
#         session.upload_file(data, key)
#     else:
#         session.put_object(Key=key, Body=data)
from utils.messageEncoder import translateMessage
from utils.properties import FILE_SUFFIXS


def upload_to_s3(key, data, complete_file=False):
    CLOUD_NAME = "mollify"
    API_KEY = "466423759736745"
    API_SECRET = "Arv-iXxAZuNrVgf3k4_nS47VFag"

    cloudinary.config(
        cloud_name=CLOUD_NAME,
        api_key=API_KEY,
        api_secret=API_SECRET
    )
    result_ = cloudinary.uploader.upload_large_part(data)
    cloudinary.logger.info("######## FILE UPLOADED TO CLOUDINARY AND SECURE URL IS {} ##################".format(
        result_.get("secure_url")))
    return result_.get("secure_url")


def return_response(data=None, message="", code=200):
    if data is None:
        data = {}
    return json.dumps({"data": data, "message": message, "code": code, "status": code, "safe": False})


def translate_message_for_mongo(userId, message):
    return translateMessage(userId, message, 'encrypt')


def error_message(error, target, message, code=500):
    return {"status_code": code,
            "content": {"error": {"message": message,
                                  "code": code,
                                  "success": False,
                                  "error": error,
                                  "target": target}}}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in FILE_SUFFIXS
