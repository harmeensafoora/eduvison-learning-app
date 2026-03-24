import os
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

client = AzureOpenAI(
    api_key=api_key,
    api_version="2024-02-15-preview",
    azure_endpoint=endpoint
)

try:
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a helpful AI."},
            {"role": "user", "content": "Say hello and confirm the connection works."}
        ],
        max_tokens=50
    )

    print("\n✅ Connection Successful!\n")
    print(response.choices[0].message.content)

except Exception as e:
    print("\n❌ Connection Failed\n")
    print(e)