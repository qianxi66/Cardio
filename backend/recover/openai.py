from pathlib import Path

import openai

from .config import openai_config

client = openai.AzureOpenAI(**openai_config)
prompt_path = Path(__file__).with_name("prompt.txt")
conversation_system_prompt = open(prompt_path, "r").read(10000000)


def gpt_inference(client: openai.OpenAI, messages, stop=None):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        max_tokens=128,
        stop=stop,
    )
    return response.choices[0].message.content


def conversation(messages):
    return gpt_inference(
        client,
        [{"role": "system", "content": conversation_system_prompt}, *messages],
    )
