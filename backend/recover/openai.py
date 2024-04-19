from pathlib import Path

import openai, json

from .config import openai_config, openai_key, symptom_descriptions

# client = openai.AzureOpenAI(**openai_config)
client = openai.OpenAI(api_key=openai_key)


prompt_path = Path(__file__).with_name("prompt.txt")
conversation_system_prompt = open(prompt_path, "r").read(10000000)
key_questions_prompt_path = Path(__file__).with_name("key_questions_prompt.txt")
key_questions_prompt = open(key_questions_prompt_path, "r").read(10000000)
summary_prompt_path = Path(__file__).with_name("summary_prompt.txt")
summary_prompt = open(summary_prompt_path, "r").read(10000000)

def gpt_inference(client: openai.OpenAI, messages, stop=None):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
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

def key_questions(messages):
    return gpt_inference(
        client,
        [{"role": "system", "content": key_questions_prompt}, {
            "role": "user", "content": messages}],
    )

def summary(messages, key_questions):
    return gpt_inference(
        client,
        [{"role": "system", "content": summary_prompt}, 
         {"role": "user", "content": "List of all symptoms descriptions"+ json.dumps(symptom_descriptions)},
         {
            "role": "user", "content": 'messages: ' + messages},
            {"role": "user", "content": 'symptoms: ' + key_questions}],
    )