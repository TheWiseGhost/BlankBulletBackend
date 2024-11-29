from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from pymongo import MongoClient
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
import boto3
from botocore.exceptions import ClientError
from bson import ObjectId
from bson.decimal128 import Decimal128
from bson.json_util import dumps
import random
import traceback
import datetime

from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import get_random_string
from django.http import JsonResponse
from pymongo import MongoClient
from pymongo.errors import OperationFailure
import bcrypt
import json
import requests

client = MongoClient(f'{settings.MONGO_URI}')
db = client['BlankBullet']
instances_collection = db['Instances']
landings_collection = db['Landings']
forms_collection = db['Forms']
checkouts_collection = db['Checkouts']
users_collection = db['Users']
aws_access_key_id = settings.AWS_ACCESS_KEY_ID
aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY

s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key)
bucket_name = 'blankbullet'

@csrf_exempt
def main(req):
    return HttpResponse("Wsg")


@csrf_exempt
def bullet_options(req):
    print('recieved')
    try:
        data = json.loads(req.body.decode("utf-8"))
        clerk_id = data.get("clerk_id")

        if not clerk_id:
            print('No clerk_id')
            return JsonResponse({'error': 'clerk_id is required'}, status=400)

        # Query the bullets collection for bullets associated with the clerk_id
        bullets = instances_collection.find({'creator_id': clerk_id})

        # Format the bullets
        formatted_bullets = [
            {'id': str(bullet['_id']), 'title': bullet['title'], 'thumbnail': bullet['thumbnail'] if "thumbnail" in bullet else ''}
            for bullet in bullets
        ]

        return JsonResponse({'bullets': formatted_bullets}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def add_bullet(req):
    try:
        print('recieved')
        clerk_id = req.POST.get('clerk_id')
        title = req.POST.get('title')
        my_file = req.FILES['file']

        date = datetime.datetime.today()

        key = f'thumbnails/{clerk_id}_{my_file.name}'

        s3.upload_fileobj(
            my_file,   # Local file path
            bucket_name,    
            key,
            ExtraArgs={'ACL': 'public-read'}
        )

        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
        

        if not clerk_id:
            print('No ClerkID')
            return JsonResponse({'error': 'clerk_id is required'})
        
        user = users_collection.find_one({'clerk_id': clerk_id})
        if not user:
            print('No User')
            return JsonResponse({'error': 'User not found'})

        landing = {
            "creator_id": clerk_id, 
            "creator_name": user['name'],
            "code": "",
        }

        form = {
            "creator_id": clerk_id, 
            "creator_name": user['name'],
            "form_data": {},
        }
        created_landing = landings_collection.insert_one(landing)
        created_form = forms_collection.insert_one(form)

        # Get the ObjectId of the inserted document
        landing_id = created_landing.inserted_id
        form_id = created_form.inserted_id

        bullet = {
            "creator_id": clerk_id,
            "creator_name": user['name'],
            'title': title,
            "created_at": date,
            "domain": "",
            "published": False,
            "thumbnail": s3_url, 
            "landing": str(landing_id),
            "form": str(form_id)
        }

        created_bullet = instances_collection.insert_one(bullet)

        # Get the ObjectId of the inserted bullet document
        bullet_id = created_bullet.inserted_id

        # Update the landing document with the bullet_id
        landings_collection.update_one(
            {'_id': landing_id},   # Filter by the landing document's _id
            {'$set': {'bullet_id': str(bullet_id)}}  # Set the bullet_id
        )
        forms_collection.update_one(
            {'_id': form_id},
            {'$set': {'bullet_id': str(bullet_id)}}
        )

        return JsonResponse({'success': True}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def bullet_details(req):
    data = json.loads(req.body.decode("utf-8"))
    clerk_id = data.get("clerk_id")
    bullet_id = data.get("bullet_id")
    
    bullet = instances_collection.find_one({"_id": ObjectId(bullet_id), "creator_id": clerk_id })
    bullet['_id'] = str(bullet['_id'])

    landing = landings_collection.find_one({"bullet_id": bullet_id, "creator_id": clerk_id })
    landing['_id'] = str(landing['_id'])

    form = forms_collection.find_one({"bullet_id": bullet_id, "creator_id": clerk_id })
    form['_id'] = str(form['_id'])

    return JsonResponse({'bullet': bullet, 'landing': landing, 'form': form}, safe=False)


@csrf_exempt
def update_landing(req):
    # Parse the incoming JSON data from the request
    data = json.loads(req.body.decode("utf-8"))
    bullet_id = data.get("bullet_id")
    clerk_id = data.get("clerk_id")
    new_code = data.get("landing_code") 
    print(new_code)

    # Check if the code is provided in the request
    if new_code is None:
        return JsonResponse({"status": "error", "message": "Code is missing from the request"})

    # Find the document matching the bullet_id and creator_id (clerk_id)
    landing = landings_collection.find_one({"bullet_id": bullet_id, "creator_id": clerk_id})

    if landing:
        # Update the 'code' field of the document that matches
        landings_collection.update_one(
            {"_id": landing["_id"]},  # Find document by its _id
            {"$set": {"code": new_code}}  # Update the code field
        )
        return JsonResponse({"status": "success", "message": "Code updated successfully"})
    else:
        print("no landing")
        return JsonResponse({"status": "error", "message": "Landing not found"})
    

@csrf_exempt
def update_form(req):
    # Parse the incoming JSON data from the request
    data = json.loads(req.body.decode("utf-8"))
    bullet_id = data.get("bullet_id")
    clerk_id = data.get("clerk_id")
    new_form = data.get("form_data") 
    print(new_form)

    # Check if the code is provided in the request
    if new_form is None:
        return JsonResponse({"status": "error", "message": "Form is missing from the request"})

    # Find the document matching the bullet_id and creator_id (clerk_id)
    form = forms_collection.find_one({"bullet_id": bullet_id, "creator_id": clerk_id})

    if form:
        # Update the 'code' field of the document that matches
        forms_collection.update_one(
            {"_id": form["_id"]},  # Find document by its _id
            {"$set": {"form_data": new_form}}  # Update the code field
        )
        return JsonResponse({"status": "success", "message": "Form updated successfully"})
    else:
        print("no landing")
        return JsonResponse({"status": "error", "message": "Form not found"})