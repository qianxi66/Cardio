from pathlib import Path

import openai

from .config import openai_config, openai_key

# client = openai.AzureOpenAI(**openai_config)
client = openai.OpenAI(api_key=openai_key)


prompt_path = Path(__file__).with_name("prompt.txt")
conversation_system_prompt = open(prompt_path, "r").read(10000000)


def gpt_inference(client: openai.OpenAI, messages, stop=None):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=512,
        stop=stop,
    )
    return response.choices[0].message.content


def conversation(messages):
    return gpt_inference(
        client,
        [{"role": "system", "content": conversation_system_prompt}, *messages],
    )
