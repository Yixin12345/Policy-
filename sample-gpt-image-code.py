

import base64
from mimetypes import guess_type

# Function to encode a local image into data URL 
def local_image_to_data_url(image_path):
    # Guess the MIME type of the image based on the file extension
    mime_type, _ = guess_type(image_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'  # Default MIME type if none is found

    # Read and encode the image file
    with open(image_path, "rb") as image_file:
        base64_encoded_data = base64.b64encode(image_file.read()).decode('utf-8')

    # Construct the data URL
    return f"data:{mime_type};base64,{base64_encoded_data}"

# Example usage
# image_path = "1.png"
# data_url = local_image_to_data_url(image_path)

############################################################################
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY", "YOUR_API_KEY_HERE"),
    base_url="https://codesense-gpt41.cognitiveservices.azure.com/openai/v1/",
)

image_path = "1.png"
data_url = local_image_to_data_url(image_path)

prompt = """perform OCR and extract fields as key value pairs from the image; 
            also perform table extract on any tables and provide the extracted table in the given format.
        """

response = client.chat.completions.create(
    model="gpt-5",
    messages=[
        { "role": "system", "content": "You are a helpful assistant." },
        { "role": "user", "content": [  
            { 
                "type": "text", 
                "text": prompt
            },
            { 
                "type": "image_url",
                "image_url": {
                    "url": data_url
                }
            }
        ] } 
    ],
    max_completion_tokens=2000 
)
print(response.choices[0].message.content)


####

# import os
# from openai import AzureOpenAI
# from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# endpoint = "https://codesense-gpt41.cognitiveservices.azure.com/"
# model_name = "gpt-5"
# deployment = "gpt-5"
# token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
# api_version = "2024-12-01-preview"

# client = AzureOpenAI(
#     api_version=api_version,
#     azure_endpoint=endpoint,
#     azure_ad_token_provider=token_provider,
# )

# response = client.chat.completions.create(
#     messages=[
#         {
#             "role": "system",
#             "content": "You are a helpful assistant.",
#         },
#         {
#             "role": "user",
#             "content": "I am going to Paris, what should I see?",
#         }
#     ],
#     max_completion_tokens=16384,
#     model=deployment
# )

# print(response.choices[0].message.content)