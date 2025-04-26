import os
from openai import OpenAI
api_keys=os.getenv("deepseek_api_key")
base_url="https://api.deepseek.com"

client=OpenAI(api_key=api_keys,base_url=base_url)
def get_key_words(question):
    response=client.chat.completions.create(
        model="deepseek-chat",
        messages=[
        {"role":"system","content":"你是一个善于提炼搜索关键词的大师，你需要从用户输入的问题中提炼出一个用于搜索的关键词，注意，你只需要返回关键词，不需要返回其他任何内容！"},
        {"role":"user","content":question}
    ]
    )
    return response.choices[0].message.content
    
if __name__=="__main__":
    question="如何使用python爬取网页数据？"
    key_words=get_key_words(question)
    print(key_words)
