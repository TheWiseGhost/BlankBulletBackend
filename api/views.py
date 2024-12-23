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
from collections import defaultdict

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
responses_collection = db['Responses']
checkout_data_collection = db['CheckoutData']
data_collection = db['Data']
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

        checkout = {
            "creator_id": clerk_id, 
            "creator_name": user['name'],
            "checkout_img": '',
            "finished_img": '',
            "finished_text": '',
            "quantities": [],
            "variants": [],
        }

        data = {
            "creator_id": clerk_id, 
            "creator_name": user['name'],
            "visitors": 0,
            "reach_form": 0,
            "reach_checkout": 0,
            "complete_checkout": 0,
        }

        created_landing = landings_collection.insert_one(landing)
        created_form = forms_collection.insert_one(form)
        created_checkout = checkouts_collection.insert_one(checkout)
        created_data = data_collection.insert_one(data)

        # Get the ObjectId of the inserted document
        landing_id = created_landing.inserted_id
        form_id = created_form.inserted_id
        checkout_id = created_checkout.inserted_id
        data_id = created_data.inserted_id

        bullet = {
            "creator_id": clerk_id,
            "creator_name": user['name'],
            'title': title,
            "created_at": date,
            "domain": "",
            "published": False,
            "thumbnail": s3_url, 
            "landing": str(landing_id),
            "form": str(form_id),
            "checkout": str(checkout_id),
            "data": str(data_id),
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
        checkouts_collection.update_one(
            {'_id': checkout_id},
            {'$set': {'bullet_id': str(bullet_id)}}
        )
        data_collection.update_one(
            {'_id': data_id},
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
    bullet_id = data.get("bullet_id")
    
    bullet = instances_collection.find_one({"_id": ObjectId(bullet_id)})
    bullet['_id'] = str(bullet['_id'])

    landing = landings_collection.find_one({"bullet_id": bullet_id})
    landing['_id'] = str(landing['_id'])

    form = forms_collection.find_one({"bullet_id": bullet_id})
    form['_id'] = str(form['_id'])

    checkout = checkouts_collection.find_one({"bullet_id": bullet_id})
    checkout['_id'] = str(checkout['_id'])

    return JsonResponse({'bullet': bullet, 'landing': landing, 'form': form, 'checkout': checkout}, safe=False)


@csrf_exempt
def update_landing(req):
    # Parse the incoming JSON data from the request
    data = json.loads(req.body.decode("utf-8"))
    bullet_id = data.get("bullet_id")
    clerk_id = data.get("clerk_id")
    new_code = data.get("landing_code") 

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
    

@csrf_exempt
def update_checkout(req):
    clerk_id = req.POST.get('clerk_id')
    bullet_id = req.POST.get('bullet_id')
    new_checkout_img = req.FILES.get('checkout_img')
    new_finished_img = req.FILES.get('finished_img')
    new_finished_text = req.POST.get('finished_text')
    new_quantities = json.loads(req.POST.get('quantities', '[]'))
    new_variants = json.loads(req.POST.get('variants', '[]'))
    new_product = req.POST.get('product')
    new_price = req.POST.get('price')

    checkout = checkouts_collection.find_one({"bullet_id": bullet_id, "creator_id": clerk_id})

    if not checkout:
        print("no checkout")
        return JsonResponse({"status": "error", "message": "Checkout not found"})

    if new_checkout_img:
        try:
            key = f'checkouts/{clerk_id}_{new_checkout_img.name}'
            s3.upload_fileobj(
                new_checkout_img,
                bucket_name,    
                key,
                ExtraArgs={'ACL': 'public-read'}
            )

            checkout_img_s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
            checkouts_collection.update_one(
                {"_id": checkout["_id"]},  # Find document by its _id
                {"$set": {"checkout_img": checkout_img_s3_url}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)

    if new_finished_img:
        try:
            key = f'checkouts/{clerk_id}_{new_finished_img.name}'
            s3.upload_fileobj(
                new_finished_img,
                bucket_name,    
                key,
                ExtraArgs={'ACL': 'public-read'}
            )

            finished_img_s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
            checkouts_collection.update_one(
                {"_id": checkout["_id"]},  # Find document by its _id
                {"$set": {"finished_img": finished_img_s3_url}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)

    if new_finished_text:
        try:
            checkouts_collection.update_one(
                {"_id": checkout["_id"]},  # Find document by its _id
                {"$set": {"finished_text": new_finished_text}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
    if new_quantities:
        try:
            checkouts_collection.update_one(
                {"_id": checkout["_id"]},  # Find document by its _id
                {"$set": {"quantities": new_quantities}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
    if new_variants:
        try:
            checkouts_collection.update_one(
                {"_id": checkout["_id"]},  # Find document by its _id
                {"$set": {"variants": new_variants}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
    if new_product:
        try:
            checkouts_collection.update_one(
                {"_id": checkout["_id"]},  # Find document by its _id
                {"$set": {"product": new_product}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
    if new_price:
        try:
            checkouts_collection.update_one(
                {"_id": checkout["_id"]},  # Find document by its _id
                {"$set": {"price": new_price}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({"status": "success", "message": "Checkout updated successfully"})


@csrf_exempt
def add_form_response(req):
    # Parse the incoming JSON data from the request
    data = json.loads(req.body.decode("utf-8"))
    bullet_id = data.get("bullet_id")
    form_response = data.get("form_response") 

    # Check if the code is provided in the request
    if form_response is None:
        return JsonResponse({"status": "error", "message": "Form is missing from the request"})

    # Find the document matching the bullet_id and creator_id (clerk_id)
    form = forms_collection.find_one({"bullet_id": bullet_id})

    if form:
        # Update the 'code' field of the document that matches
        date = datetime.datetime.today()

        formatted_response = {
            "bullet_id": bullet_id,
            'form_id': str(form['_id']),
            "created_at": date,
            "response": form_response
        }

        responses_collection.insert_one(formatted_response)

        return JsonResponse({"status": "success", "message": "Response added"})
    else:
        print("no landing")
        return JsonResponse({"status": "error", "message": "Form not found"})
    

@csrf_exempt
def add_checkout_data(req):
    # Parse the incoming JSON data from the request
    data = json.loads(req.body.decode("utf-8"))
    bullet_id = data.get("bullet_id")
    checkout_response = data.get("checkout_response") 

    # Check if the code is provided in the request
    if checkout_response is None:
        return JsonResponse({"status": "error", "message": "Form is missing from the request"})

    # Find the document matching the bullet_id and creator_id (clerk_id)
    checkout = checkouts_collection.find_one({"bullet_id": bullet_id})

    if checkout:
        # Update the 'code' field of the document that matches
        date = datetime.datetime.today()

        formatted_response = {
            "bullet_id": bullet_id,
            'checkout_id': str(checkout['_id']),
            "created_at": date,
            "data": checkout_response
        }

        checkout_data_collection.insert_one(formatted_response)

        return JsonResponse({"status": "success", "message": "Response added"})
    else:
        print("no landing")
        return JsonResponse({"status": "error", "message": "Form not found"})
    

@csrf_exempt
def update_data(req):
    try:
        data = json.loads(req.body.decode("utf-8"))
        bullet_id = data.get("bullet_id")
        page = data.get("page")

        if not bullet_id or not page:
            return JsonResponse({"error": "Missing bullet_id or page in request."}, status=400)

        # Define the field to increment based on the page
        field_map = {
            "landing": "visitors",
            "form": "reach_form",
            "checkout": "reach_checkout",
            "finished": "complete_checkout"
        }

        if page in field_map:
            result = data_collection.update_one(
                {"bullet_id": bullet_id},  # Query to match the document
                {"$inc": {field_map[page]: 1}}  # Increment the appropriate field
            )

            if result.matched_count > 0:
                return JsonResponse({"message": "Field updated successfully."}, status=200)
            else:
                return JsonResponse({"error": "Document not found."}, status=404)
        else:
            return JsonResponse({"error": "Invalid page value."}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    

@csrf_exempt
def get_analytics(req):
    try:
        data = json.loads(req.body.decode("utf-8"))
        clerk_id = data.get("clerk_id")
        bullet_id = data.get("bullet_id")

        if not clerk_id or not bullet_id:
            return JsonResponse({"error": "clerk_id and bullet_id are required."}, status=400)

        # Fetch checkout data
        checkout_data = list(checkout_data_collection.find({"bullet_id": bullet_id}))
        for checkout in checkout_data:
            checkout['_id'] = str(checkout['_id'])

        # Fetch responses data
        responses = list(responses_collection.find({"bullet_id": bullet_id}))
        for response in responses:
            response['_id'] = str(response['_id'])

        bullet_data = data_collection.find_one({"bullet_id": bullet_id, "creator_id": clerk_id})
        bullet_data['_id'] = str(bullet_data['_id'])

        # Aggregate analytics for responses
        answer_counts = defaultdict(lambda: defaultdict(int))

        for response in responses:
            response_data = response.get('response', {})  # Assume 'response' contains {question: answer}
            for question, answer in response_data.items():
                answer_counts[question][answer] += 1

        # Prepare analytics data in a readable format
        form_analytics = {
            question: dict(answers) for question, answers in answer_counts.items()
        }

        return JsonResponse({
            'checkout_data': checkout_data,
            'responses': responses,
            'form_analytics': form_analytics,
            'bullet_data': bullet_data,
        }, safe=False)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data."}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)
