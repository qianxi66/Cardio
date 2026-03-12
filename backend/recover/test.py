from openai import AzureOpenAI

endpoint = "https://bosu-mljmcbpq-eastus2.cognitiveservices.azure.com/"
deployment = "gpt-5.2"
api_version = "2025-04-01-preview"
api_key = "945UEiQPWM5eDL5mvVcnU6Cjov4q84021866Ii1kPQyAkvhV90uGJQQJ99CBACHYHv6XJ3w3AAAAACOG0qNc"

# Create Azure OpenAI client
client = AzureOpenAI(
    api_key=api_key,
    api_version=api_version,
    azure_endpoint=endpoint
)

# Send chat request
response = client.chat.completions.create(
    model=deployment,
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Have you eaten?"
        }
    ],
    max_completion_tokens=200
)

# Print model reply to terminal
print(response.choices[0].message.content)