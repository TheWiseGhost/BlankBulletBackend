from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
from django.conf import settings
import boto3
from bson import ObjectId
import traceback
import datetime
from collections import defaultdict

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from pymongo import MongoClient
import json
import re
import stripe

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
def drop_options(req):
    print('recieved')
    try:
        data = json.loads(req.body.decode("utf-8"))
        clerk_id = data.get("clerk_id")

        if not clerk_id:
            print('No clerk_id')
            return JsonResponse({'error': 'clerk_id is required'}, status=400)

        # Query the drops collection for drops associated with the clerk_id
        drops = instances_collection.find({'creator_id': clerk_id})

        # Format the drops
        formatted_drops = [
            {'id': str(drop['_id']), 'title': drop['title'], 'thumbnail': drop['thumbnail'] if "thumbnail" in drop else ''}
            for drop in drops
        ]

        return JsonResponse({'drops': formatted_drops}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def add_drop(req):
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
            "brand_name": "",
            "product_title": "",
            "price": "",
            "logo": "",
            "primary_img": "",
            "other_img1": "",
            "other_img2": "",
            "other_img3": "",
            "cta": "",
            "variants": [],
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

        drop = {
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

        created_drop = instances_collection.insert_one(drop)

        # Get the ObjectId of the inserted drop document
        drop_id = created_drop.inserted_id

        # Update the landing document with the drop_id
        landings_collection.update_one(
            {'_id': landing_id},   # Filter by the landing document's _id
            {'$set': {'drop_id': str(drop_id)}}  # Set the drop_id
        )
        forms_collection.update_one(
            {'_id': form_id},
            {'$set': {'drop_id': str(drop_id)}}
        )
        checkouts_collection.update_one(
            {'_id': checkout_id},
            {'$set': {'drop_id': str(drop_id)}}
        )
        data_collection.update_one(
            {'_id': data_id},
            {'$set': {'drop_id': str(drop_id)}}
        )

        users_collection.update_one(
            {'clerk_id': clerk_id},
            {'$inc': {'num_active_drops': 1}}
        )

        return JsonResponse({'success': True}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def drop_details(req):
    data = json.loads(req.body.decode("utf-8"))
    drop_id = data.get("drop_id")
    
    drop = instances_collection.find_one({"_id": ObjectId(drop_id)})
    drop['_id'] = str(drop['_id'])

    landing = landings_collection.find_one({"drop_id": drop_id})
    landing['_id'] = str(landing['_id'])

    form = forms_collection.find_one({"drop_id": drop_id})
    form['_id'] = str(form['_id'])

    checkout = checkouts_collection.find_one({"drop_id": drop_id})
    checkout['_id'] = str(checkout['_id'])

    return JsonResponse({'drop': drop, 'landing': landing, 'form': form, 'checkout': checkout}, safe=False)


@csrf_exempt
def update_landing(req):
    clerk_id = req.POST.get('clerk_id')
    drop_id = req.POST.get('drop_id')
    new_logo = req.FILES.get('logo')
    new_primary_img = req.FILES.get('primary_img')
    new_other_img1 = req.FILES.get('other_img1')
    new_other_img2 = req.FILES.get('other_img2')
    new_other_img3 = req.FILES.get('other_img3')
    new_product_title = json.loads(req.POST.get('product_title'))
    new_brand_name = json.loads(req.POST.get('brand_name'))
    new_cta = json.loads(req.POST.get('cta'))
    new_variants = req.POST.get('variants', '[]')
    new_price = json.loads(req.POST.get('price'))

    landing = landings_collection.find_one({"drop_id": drop_id, "creator_id": clerk_id})

    if not landing:
        print("no landing")
        return JsonResponse({"status": "error", "message": "Landing not found"})

    if new_primary_img:
        try:
            key = f'landings/{clerk_id}_{new_primary_img.name}'
            s3.upload_fileobj(
                new_primary_img,
                bucket_name,    
                key,
                ExtraArgs={'ACL': 'public-read'}
            )

            primary_img_s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"primary_img": primary_img_s3_url}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)

    if new_other_img1:
        try:
            key = f'landings/{clerk_id}_{new_other_img1.name}'
            s3.upload_fileobj(
                new_other_img1,
                bucket_name,    
                key,
                ExtraArgs={'ACL': 'public-read'}
            )

            other_img1_s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"other_img1": other_img1_s3_url}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
    if new_other_img2:
        try:
            key = f'landings/{clerk_id}_{new_other_img2.name}'
            s3.upload_fileobj(
                new_other_img2,
                bucket_name,    
                key,
                ExtraArgs={'ACL': 'public-read'}
            )

            other_img2_s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"other_img2": other_img2_s3_url}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
    if new_other_img3:
        try:
            key = f'landings/{clerk_id}_{new_other_img3.name}'
            s3.upload_fileobj(
                new_other_img3,
                bucket_name,    
                key,
                ExtraArgs={'ACL': 'public-read'}
            )

            other_img3_s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"other_img3": other_img3_s3_url}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)

    if new_product_title:
        try:
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"product_title": new_product_title}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
    if new_logo:
        try:
            key = f'landings/{clerk_id}_{new_logo.name}'
            s3.upload_fileobj(
                new_logo,
                bucket_name,    
                key,
                ExtraArgs={'ACL': 'public-read'}
            )

            logo_s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"logo": logo_s3_url}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
        
    if new_brand_name:
        try:
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"brand_name": new_brand_name}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)

        
    if new_variants:
        try:
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"variants": new_variants.split(",")}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
        
    if new_price:
        try:
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"price": new_price}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
        
    if new_cta:
        try:
            landings_collection.update_one(
                {"_id": landing["_id"]},  # Find document by its _id
                {"$set": {"cta": new_cta}}  # Update the fields
            )
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({"status": "success", "message": "Checkout updated successfully"})
    

@csrf_exempt
def update_form(req):
    # Parse the incoming JSON data from the request
    data = json.loads(req.body.decode("utf-8"))
    drop_id = data.get("drop_id")
    clerk_id = data.get("clerk_id")
    new_form = data.get("form_data") 

    # Check if the code is provided in the request
    if new_form is None:
        return JsonResponse({"status": "error", "message": "Form is missing from the request"})

    # Find the document matching the drop_id and creator_id (clerk_id)
    form = forms_collection.find_one({"drop_id": drop_id, "creator_id": clerk_id})

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
    drop_id = req.POST.get('drop_id')
    new_checkout_img = req.FILES.get('checkout_img')
    new_finished_img = req.FILES.get('finished_img')
    new_finished_text = req.POST.get('finished_text')
    new_quantities = json.loads(req.POST.get('quantities', '[]'))
    new_variants = json.loads(req.POST.get('variants', '[]'))
    new_product = req.POST.get('product')
    new_price = req.POST.get('price')

    checkout = checkouts_collection.find_one({"drop_id": drop_id, "creator_id": clerk_id})

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
    drop_id = data.get("drop_id")
    form_response = data.get("form_response") 

    # Check if the code is provided in the request
    if form_response is None:
        return JsonResponse({"status": "error", "message": "Form is missing from the request"})

    # Find the document matching the drop_id and creator_id (clerk_id)
    form = forms_collection.find_one({"drop_id": drop_id})

    if form:
        # Update the 'code' field of the document that matches
        date = datetime.datetime.today()

        formatted_response = {
            "drop_id": drop_id,
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
    drop_id = data.get("drop_id")
    checkout_response = data.get("checkout_response") 

    # Check if the code is provided in the request
    if checkout_response is None:
        return JsonResponse({"status": "error", "message": "Form is missing from the request"})

    # Find the document matching the drop_id and creator_id (clerk_id)
    checkout = checkouts_collection.find_one({"drop_id": drop_id})

    if checkout:
        # Update the 'code' field of the document that matches
        date = datetime.datetime.today()

        formatted_response = {
            "drop_id": drop_id,
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
        drop_id = data.get("drop_id")
        page = data.get("page")

        if not drop_id or not page:
            return JsonResponse({"error": "Missing drop_id or page in request."}, status=400)

        # Define the field to increment based on the page
        field_map = {
            "landing": "visitors",
            "form": "reach_form",
            "checkout": "reach_checkout",
            "finished": "complete_checkout"
        }

        if page in field_map:
            result = data_collection.update_one(
                {"drop_id": drop_id},  # Query to match the document
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
        drop_id = data.get("drop_id")

        if not clerk_id or not drop_id:
            return JsonResponse({"error": "clerk_id and drop_id are required."}, status=400)

        # Fetch checkout data
        checkout_data = list(checkout_data_collection.find({"drop_id": drop_id}))
        for checkout in checkout_data:
            checkout['_id'] = str(checkout['_id'])

        # Fetch responses data
        responses = list(responses_collection.find({"drop_id": drop_id}))
        for response in responses:
            response['_id'] = str(response['_id'])

        drop_data = data_collection.find_one({"drop_id": drop_id, "creator_id": clerk_id})
        drop_data['_id'] = str(drop_data['_id'])

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
            'drop_data': drop_data,
        }, safe=False)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data."}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)


@csrf_exempt
def add_domain(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            drop_id = data.get("drop_id")
            clerk_id = data.get("clerk_id")
            domain = data.get("domain")

            if not drop_id or not clerk_id or not domain:
                return JsonResponse({"error": "Site ID and domain are required."}, status=400)
            
            DOMAIN_REGEX = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"

            if not re.match(DOMAIN_REGEX, domain):
                return JsonResponse({"error": "Invalid domain format."}, status=400)

            instances_collection.update_one(
                {"_id": ObjectId(drop_id), "creator_id": clerk_id},
                {"$set": {"domain": domain, "published": True}},
            )

            return JsonResponse({"message": "Domain successfully mapped."})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)


@csrf_exempt
def user_details(req):
    try:
        # Parse the request body
        data = json.loads(req.body)
        clerk_id = data.get("clerk_id")

        if not clerk_id:
            return JsonResponse({"error": "clerk_id is required"}, status=400)

        # Find the user in the database
        user = users_collection.find_one({'clerk_id': clerk_id})
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        # Convert ObjectId to string
        user['_id'] = str(user['_id'])

        return JsonResponse({'user': user})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)



# STRIPE CHECKOUT STUFF

# Set Stripe API key
stripe.api_key = settings.STRIPE_SK

# Stripe webhook secret
WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET

@csrf_exempt
def create_checkout_session(request):
    """
    Creates a Stripe Checkout Session for one-time payments.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            product_id = data.get("product_id")
            user_id = data.get("user_id")
            print(user_id)

            # Product price mapping in cents (e.g., $5 = 500 cents)
            product_to_price_mapping = {
                "prod_RbKH6n0xMLncqe": "price_1Qi7d0EDEXUqncIqb4uC08Wb",   # $5
                "prod_RbKIjVji5glZrB": "price_1Qi7dsEDEXUqncIqzC3EVT2k",  # $15
            }

            if product_id not in product_to_price_mapping:
                return JsonResponse({"error": "Invalid Product ID"}, status=400)

            # Create a Stripe Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": product_to_price_mapping[product_id],
                        "quantity": 1,
                    }
                ],
                mode="payment",  # One-time payment mode
                success_url="https://trydropfast.com/dashboard",
                cancel_url="https://trydropfast.com/dashboard",
                metadata={
                    "user_id": user_id,  # Attach user ID as metadata
                    "product_id": product_id,  # Attach product ID as metadata
                }
            )

            return JsonResponse({"url": session.url})

        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def stripe_webhook(request):
    """
    Handles Stripe webhook events.
    """
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as e:
        # Signature doesn't match
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    # Handle checkout.session.completed
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        handle_checkout_session(session)

    return JsonResponse({"status": "success"}, status=200)


def handle_checkout_session(session):
    """
    Processes the checkout session completion event.
    """
    user_id = session["metadata"].get("user_id")
    product_id = session["metadata"].get("product_id")

    # Map product_id to ad credits
    product_to_credit = {
        "prod_RbKH6n0xMLncqe": 1,
        "prod_RbKIjVji5glZrB": 6,
    }

    credit = product_to_credit.get(product_id, 0)
    # ad_credit_value = Decimal128(Decimal(credit)).to_decimal()

    if user_id:
        user = users_collection.find_one({'clerk_id': user_id})
    else:
        print("no user id")    

    if user and credit > 0:
        try:
            users_collection.update_one({'clerk_id': user_id}, {
                        '$inc': {'num_drops': credit}
                    })
            print(f"Added {credit} drops to user {user_id}.")
        except Exception as e:
            print(f"Failed to update MongoDB: {e}")
