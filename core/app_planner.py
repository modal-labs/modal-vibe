"""App Planner is in charge of planning the execution of an app creation or an app edit."""

import anthropic
from pydantic import BaseModel

from core.llm import generate_response

APP_BACKEND_PORT = 8001

class AppPlan(BaseModel):
    overview: str
    frontend_plan: str
    backend_plan: str

EXAMPLE_PLAN_PROMPT = """
Features:
- View a catalog of flowers (bouquets, single stems, potted plants)
- Add flowers to a shopping cart
- Checkout + order confirmation

Backend (FastAPI)
API Routes:
- GET /api/products
- GET /api/products/{id}
- POST /api/cart
- POST /api/checkout
- GET /api/orders/{id}

Models
- Product: id, name, description, price, image_url, stock, category
- CartItem: product_id, quantity
- Order: id, items, total, customer_info, order_status
- User: id, name, email, password_hash (optional for login)
"""

class AppPlan(BaseModel):
    overview: str
    frontend_component: str
    backend_code: str


class AppPlanner:
    is_init: bool = False
    plan: AppPlan
    
    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self.plan = AppPlan(overview="", frontend_component="", backend_code="")

    async def generate(self, prompt: str) -> AppPlan:
        self.plan.overview = await self._generate_plan_overview(prompt)
        self.plan.backend_code = await self._generate_backend_code(self.plan.overview)
        self.plan.frontend_component = await self._generate_frontend_code(self.plan.overview)

    def explain(
        self, message: str, original_plan: "AppPlan", new_plan: "AppPlan"
    ):
        if self.is_init:
            prompt = f"""
            You are Jeffrey Zeldman's top web designer. You were given the following prompt and you generated the following plan:

            Prompt: {message}

            You generated the following change plan: {self.plan}

            Give a response that summarizes the changes you made. An example of a good response is:
            - "That sounds great! I made a donut chart for you. Let me know if you want anything else!"

            Be as concise as possible, but always be friendly!
            """
        else: 
            prompt = f"""
        You generated the following change plan to the prompt:

        Prompt: {message}

        Original change plan: {original_plan}
    
        Generated change plan: {new_plan}
    

        Give a response that summarizes the changes you made. An example of a good response is:
        - "Sounds good! I've made the changes you requested. Yay :D"
        - "I colored the background red and added a new button. Let me know if you want anything else!"
        - "I updated the font to a more modern one and added a new section. Cheers!!"

        Be as concise as possible, but always be friendly!
        """
        
        explaination = generate_response(
            self.client,
            prompt,
            model="claude-3-5-haiku-20241022",
            max_tokens=128,
        )
        return explaination


    async def _generate_plan_overview(self, prompt: str) -> str:
        if self.is_init:
            prompt = f"""
You are a full stack developer. You are given the following prompt and your job is to come up with a plan for a single page full stack web application that is a good example of the prompt.

The backend is a fastapi webserver.
The frontend is a React application using Tailwind CSS.

Come up with a broad plan on how to build the application.
- Overall application features
- API routes supplied by the backend
- Frontend features to include

Project request:
{prompt}

RESPONSE FORMAT:
{EXAMPLE_PLAN_PROMPT}
            """
        else:
            prompt = f"""
You are a full stack developer. You are given the following prompt, an existing application, and your job is to create an action plan to transform the existing application to be a good example of the prompt.


The backend is a fastapi webserver.
The frontend is a React application using Tailwind CSS.

Project request:
{prompt}

Existing application:
    - Backend code:
    {self.plan.backend_code}

    - Frontend code:
    {self.plan.frontend_component}

RESPONSE FORMAT:
{EXAMPLE_PLAN_PROMPT}
            """
        response = generate_response(self.client, prompt)
        return response

    async def _generate_backend_code(self, message: str) -> str:
        prompt = f"""
You are a backend developer. You have been given the following plan for a full stack web application and your job is to write the FastAPI server corresponding to the backend portion of the plan.

{message}

{f"Original backend code: {self.plan.backend_code}" if not self.is_init else ""}

Generate a single page FastAPI server. Do not include any other text in your response. Only the FastAPI server code.

RESPONSE FORMAT:
import fastapi

app = fastapi.FastAPI()

@app.get("/")
def read_root():
    return {{"message": "Hello, World!"}}
            """
        response = generate_response(self.client, prompt)
        print(f"Generated backend code: {response}")
        return response
    
    async def _generate_frontend_code(self, message: str) -> str:
        html_gen_prompt = (
            f"""
        You are a frontend developer. You have been given the following plan for a full stack web application and your job is to write the React component corresponding to the frontend portion of the plan.

        The existing React component you are working with is this.
        {self.plan.frontend_component}

        You have access to the following API routes at port {APP_BACKEND_PORT}
        {self.plan.backend_code}

        You are asked to make the following changes to the React component:
        {message}
        """
            if not self.is_init
            else f"""
        You are asked to generate a React component that is a good example of the prompt.
        Prompt: {message}
        """
        )

        prompt = f"""
        You are Jeffrey Zeldman's top web designer. You are given the following prompt and your job is to generate a React component that is a good example of the prompt.
        You should use Tailwind CSS for styling. Please make sure to export the component as default.
        This is incredibly important for my job, please be careful and don't make any mistakes.
        Make sure you import all necessary dependencies.

        Prompt: {message}

        {html_gen_prompt}

        RESPONSE FORMAT:
        import React from 'react';
        export default function LLMComponent() {{
            return (
                <div className="bg-red-500">
                    <h1>LLM Component</h1>
                </div>
            )
        }}

        DO NOT include any other text in your response. Only the React component.
        """
        response = generate_response(self.client, prompt)
        print(f"Generated frontend code: {response}")
        return response
    
