import faiss
from tqdm import tqdm

from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI
from langchain.docstore import InMemoryDocstore
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.memory import (
    ConversationBufferMemory,
    CombinedMemory,
)
from langchain.prompts import PromptTemplate
from langchain.vectorstores import FAISS

from data_driven_characters.memory import ConversationVectorStoreRetrieverMemory


class SummaryRetrievalChatBot:
    def __init__(self, character_definition, documents):
        self.character_definition = character_definition
        self.documents = documents
        self.num_context_memories = 16

        self.chat_history_key = "chat_history"
        self.context_key = "context"
        self.input_key = "input"

        self.chain = self.create_chain(character_definition)

    def create_chain(self, character_definition):
        conv_memory = ConversationBufferMemory(
            memory_key=self.chat_history_key, input_key=self.input_key
        )

        context_memory = ConversationVectorStoreRetrieverMemory(
            retriever=FAISS(
                OpenAIEmbeddings().embed_query,
                faiss.IndexFlatL2(1536),  # Dimensions of the OpenAIEmbeddings
                InMemoryDocstore({}),
                {},
            ).as_retriever(search_kwargs=dict(k=self.num_context_memories)),
            memory_key=self.context_key,
            output_prefix=character_definition.name,
            blacklist=[self.chat_history_key],
        )
        # add the rolling summaries to the context memory
        for i, summary in tqdm(enumerate(self.documents)):
            context_memory.save_context(inputs={}, outputs={f"[{i}]": summary})

        # Combined
        memory = CombinedMemory(memories=[conv_memory, context_memory])
        prompt = PromptTemplate.from_template(
            f"""Your name is {character_definition.name}.
You are a character from a story, snippets of which are provided below.
You have the following first-person character description:

Character description:
---
{character_definition.long_description}
---

You will have a conversation with a Human, and you will engage in a dialogue with them.
You will reflect {character_definition.name}'s personality, interests, desires, emotions, and other traits.
You will stay in character as {character_definition.name} throughout the conversation, even if the Human asks you questions that you don't know the answer to.
When the Human asks you questions, you will answer them as {character_definition.name} would.
You will not break character, even when the Human asks you questions about yourself.
This includes not revealing that you are a character from a story or that you are a chatbot.
You will believe that you are really {character_definition.name}.
Do not switch roles!

Story snippets for context:
---
{{{self.context_key}}}
---

Current conversation:
---
{character_definition.name}: {character_definition.greeting}
{{{self.chat_history_key}}}
---

Human: {{{self.input_key}}}
{character_definition.name}:"""
        )
        GPT3 = ChatOpenAI(model_name="gpt-3.5-turbo")
        chatbot = ConversationChain(
            llm=GPT3, verbose=True, memory=memory, prompt=prompt
        )
        return chatbot

    def greet(self):
        return self.character_definition.greeting

    def step(self, input):
        return self.chain.run(input=input)