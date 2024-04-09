import cv2
import os
import time
import re
import pytesseract
from pytesseract import Output
import numpy as np
import requests
from datetime import datetime, timedelta

####################Constants#########################

# Filter for image recognition
img_config = r"--psm 11 --oem 3"
pattern = re.compile("[0-9]+")
# Directory to save the images
save_directory = '/home/bailthom/Pictures/Magic_Cards/'
img_name = 'captured_image.jpg'
img_path = os.path.join(save_directory, img_name)
#Directory for Scryfall database
database_location = '/home/bailthom/Documents/Scryfall/'
database_destination = ''
#Camera
camera = cv2.VideoCapture(0)

####################Settings##########################

# Create the directory if it doesn't exist
if not os.path.exists(save_directory):
    os.makedirs(save_directory)
    
# Check if the camera is opened successfully
if not camera.isOpened():
    print("Error: Could not open camera.")
    exit()

####################Functions#########################
    
# Download all Default Cards from scryfall in order to limit API utilization
def download_all_cards_file():
    # URL of the "Default Cards" data from Scryfall Bulk Data service
    max_age = timedelta(days=7) #redownload file each week
    url = "https://api.scryfall.com/bulk-data/default-cards"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            download_uri = data['download_uri']
            
            # Extract filename from the download URI
            filename = 'Scryfall_Database'
            database_destination = os.path.join(database_location, filename)

            # Create the directory if it doesn't exist
            os.makedirs(database_location, exist_ok=True)

            # Check if the file exists and its last modified time
            if os.path.exists(database_destination):
                file_modified_time = datetime.fromtimestamp(os.path.getmtime(database_destination))
                current_time = datetime.now()
                age = current_time - file_modified_time
 
                # If the file is less than 1 week old, do not download again
                if age < max_age:
                    print("File already exists and is less than 1 week old. No need to download.")
                    return
                
            # Download the file
            print("Downloading cards. Please do not exit program...")
            response = requests.get(download_uri)
            if response.status_code == 200:
                with open(database_destination, 'wb') as f:
                    f.write(response.content)
                print("Default Cards data downloaded successfully.")
            else:
                print("Failed to download Default Cards data. Status code:", response.status_code)
        else:
            print("Failed to retrieve download URI. Status code:", response.status_code)
    except Exception as e:
        print("Failed to download Default Cards data:", e)

# Search Scryfall API for card information by the card name
def search_card_by_name(card_name):
    url = f"https://api.scryfall.com/cards/named?fuzzy={card_name}"
    response = requests.get(url)
    if response.status_code == 200:
        card_data = response.json()
        return card_data
    elif response.status_code == 404:
        print("Card not found. ", card_name)
        return None
    else:
        print(f"Error: {response.status_code}")
        return None

# Search Scryfall API for card information from the set code and collectors code
def search_card_by_collector_number(set_code, collector_number):
    url = f"https://api.scryfall.com/cards/search?q=set:{set_code} cn:{collector_number}"
    response = requests.get(url)
    if response.status_code == 200:
        search_results = response.json()
        if search_results['data']:
            return search_results['data'][0]  # Return the first result
        else:
            print("Card not found.")
            return None
    else:
        print("Failed to search for card.")
        return None

# Display the card information from the pulled card
def display_card_details(card_data):
    if card_data:
        print("Card Name:", card_data['name'])
        print("Card Type:", card_data['type_line'])
        print("Set:", card_data['set_name'])
        print("Mana Cost:", card_data['mana_cost'])
        print("Mana Value:", card_data['cmc'])
        print("Colors:", card_data['colors'])
        print("Oracle Text:", card_data['oracle_text'])
    else:
        print("No card details to display.")
        
# Verifys the card name starts on a capital letter
def remove_improper_prefix(card_name):
    for i, char in enumerate(card_name):
        if char.isupper():
            return card_name[i:]
    return ''
# Verifys the card name ends on a lowercase letter
def remove_improper_suffix(card_name):
    for i in range(len(card_name) - 1, -1, -1):
        if card_name[i].islower():
            return card_name[:i+1]
    return ''

####################Main############################

try:
    while True:
        #Download the Scryfall database to limit api call usage
        download_all_cards_file()
        #search_by = input("Please enter how you wish to search for your cards: \nCard Name\nCollectors ID\n")
        search_by = "Card Name"
        
        # Capture card image
        for _ in range(10):
            camera.grab()
        ret, frame = camera.read()
        if not ret:
            print("Error: Unable to capture frame.")
            break
        
        # Save the captured image
        cv2.imwrite(img_path, frame)
        
        # Resize image to focus on card name location
        height, width, _ = frame.shape
        resize_height, resize_width = int(height * 0.105), int(width*0.8)
        start_x, start_y = int(frame.shape[1] * 0.215), int(frame.shape[0] * 0.6)
        end_x, end_y = start_x + resize_width, start_y + resize_height
        roi = frame[start_y:end_y, start_x:end_x]
        resize_img = cv2.resize(roi, (resize_width, resize_height))
        cv2.imwrite(img_path, resize_img)
        
        # Greyscale image to improve contrast
        greyscale_image = cv2.cvtColor(resize_img, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(img_path, greyscale_image)
        
        # Add binary threshold to highly contrast text
        _, result = cv2.threshold(greyscale_image, 20,255, cv2.THRESH_BINARY)
        edges = cv2.adaptiveThreshold(greyscale_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 255, 35)
        cv2.imwrite(img_path, edges)
        
        # Attempt to read text from saved image
        if search_by == "Card Name":
            card_name = pytesseract.image_to_string(img_path)
            card_data = None
            timeout = 0
            while not card_name:
                time.sleep(0.1)
                card_name = pytesseract.image_to_string(img_path)
                timeout += 1
                if timeout >= 10:
                    break
            if not card_name:
                print(f"Failed to read a card name within {timeout} attempts.")
            else:
                remove_improper_prefix(card_name)
                remove_improper_suffix(card_name)
                card_data = search_card_by_name(card_name)
            display_card_details(card_data)
            
        # Wait for the operator to press Enter before continuing
        input("Press Enter to continue...")

except KeyboardInterrupt:
    print("Keyboard interrupt detected. Exiting...")
finally:
    # Release the camera
    camera.release()
