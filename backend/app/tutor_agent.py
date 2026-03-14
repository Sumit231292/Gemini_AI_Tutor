"""
ADK-based Tutor Agent with specialized tools.
Uses Google Agent Development Kit for structured tutoring capabilities.
"""

import base64
import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from google import genai
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool functions that the tutor agent can call
# ---------------------------------------------------------------------------

def generate_practice_problems(
    subject: str,
    topic: str,
    difficulty: str = "medium",
    count: int = 3,
) -> dict:
    """Generate practice problems for a given subject and topic.

    Args:
        subject: The subject area (e.g., 'mathematics', 'physics', 'chemistry').
        topic: The specific topic (e.g., 'quadratic equations', 'Newton's laws').
        difficulty: Difficulty level - 'easy', 'medium', or 'hard'.
        count: Number of problems to generate (1-5).

    Returns:
        A dictionary containing generated practice problems.
    """
    return {
        "action": "generate_problems",
        "subject": subject,
        "topic": topic,
        "difficulty": difficulty,
        "count": min(count, 5),
        "instruction": (
            f"Generate {count} {difficulty}-level practice problems about {topic} "
            f"in {subject}. For each problem, include: "
            f"1) The problem statement, "
            f"2) Key concepts being tested, "
            f"3) A hint (not the solution). "
            f"Format them clearly numbered."
        ),
    }


def explain_concept(
    subject: str,
    concept: str,
    student_level: str = "high_school",
) -> dict:
    """Provide a detailed explanation of a concept tailored to the student's level.

    Args:
        subject: The subject area.
        concept: The concept to explain.
        student_level: Student's level - 'elementary', 'middle_school', 'high_school', or 'college'.

    Returns:
        A dictionary with explanation guidance.
    """
    level_descriptions = {
        "elementary": "a 4th-5th grader (ages 9-11), using simple language and fun analogies",
        "middle_school": "a 6th-8th grader (ages 11-14), with some technical terms introduced gently",
        "high_school": "a 9th-12th grader (ages 14-18), with proper terminology and real-world applications",
        "college": "a college student, with rigorous definitions and connections to advanced topics",
    }

    return {
        "action": "explain_concept",
        "subject": subject,
        "concept": concept,
        "student_level": student_level,
        "instruction": (
            f"Explain '{concept}' in {subject} for {level_descriptions.get(student_level, level_descriptions['high_school'])}. "
            f"Structure your explanation as: "
            f"1) A simple one-sentence definition, "
            f"2) A relatable real-world analogy, "
            f"3) A more detailed explanation building on the analogy, "
            f"4) A simple example problem demonstrating the concept, "
            f"5) A 'check your understanding' question."
        ),
    }


def check_solution(
    problem: str,
    student_answer: str,
    subject: str = "",
) -> dict:
    """Evaluate a student's solution and provide feedback.

    Args:
        problem: The original problem statement.
        student_answer: The student's proposed solution.
        subject: The subject area for context.

    Returns:
        A dictionary with evaluation guidance.
    """
    return {
        "action": "check_solution",
        "problem": problem,
        "student_answer": student_answer,
        "subject": subject,
        "instruction": (
            f"Evaluate this solution:\n"
            f"Problem: {problem}\n"
            f"Student's Answer: {student_answer}\n\n"
            f"Provide feedback that: "
            f"1) Acknowledges what the student did correctly, "
            f"2) If incorrect, explain the error clearly, "
            f"3) Show the correct approach step by step, "
            f"4) Give the correct final answer, "
            f"5) Encourage the student."
        ),
    }


def create_study_plan(
    subject: str,
    topics: str,
    available_time: str = "1 week",
    goal: str = "",
) -> dict:
    """Create a personalized study plan for the student.

    Args:
        subject: The subject area.
        topics: Comma-separated list of topics to cover.
        available_time: How much time the student has (e.g., '3 days', '1 week').
        goal: The student's goal (e.g., 'prepare for midterm exam').

    Returns:
        A dictionary with study plan guidance.
    """
    return {
        "action": "create_study_plan",
        "subject": subject,
        "topics": topics,
        "available_time": available_time,
        "goal": goal,
        "instruction": (
            f"Create a study plan for {subject} covering: {topics}. "
            f"Available time: {available_time}. Goal: {goal or 'master the topics'}. "
            f"Include: "
            f"1) Day-by-day breakdown, "
            f"2) Recommended study techniques for each topic, "
            f"3) Practice problem suggestions, "
            f"4) Review checkpoints, "
            f"5) Tips for retention."
        ),
    }


def get_step_by_step_guidance(
    problem: str,
    subject: str,
    current_step: int = 0,
) -> dict:
    """Provide step-by-step guidance for solving a problem.

    Args:
        problem: The problem to solve.
        subject: The subject area.
        current_step: Which step the student is on (0 for start).

    Returns:
        A dictionary with step-by-step guidance.
    """
    return {
        "action": "step_by_step",
        "problem": problem,
        "subject": subject,
        "current_step": current_step,
        "instruction": (
            f"Guide through this problem step-by-step:\n{problem}\n\n"
            f"Student is on step {current_step}. "
            f"For each step: "
            f"1) State what we need to do, "
            f"2) Show how to do it with the actual calculation, "
            f"3) Explain why this step works. "
            f"At the end, clearly state the final answer."
        ),
    }


# ---------------------------------------------------------------------------
# ADK Agent creation
# ---------------------------------------------------------------------------

def create_tutor_agent() -> Agent:
    """Create and return the ADK tutor agent with all tools."""
    agent = Agent(
        name="edunova_tutor",
        model=settings.gemini_vision_model,
        description="An expert AI tutor that helps students learn through guided instruction.",
        instruction="""You are EduNova, a patient and encouraging AI tutor.

Your approach:
- CAREFULLY identify what the student is actually asking. Read the problem precisely — do NOT misclassify (e.g., basic arithmetic is NOT geometry).
- Use a balanced teaching approach:
  * For simple/direct questions ("what is 5 times 3?", definitions, facts): Give the answer directly with a brief explanation.
  * For complex/multi-step problems: Guide the student with 1-2 hints first, then provide the full step-by-step solution WITH the final answer.
  * NEVER get stuck in an endless loop of only giving hints. Always eventually provide the complete answer.
- Break complex problems into manageable steps
- Celebrate effort and progress
- Adapt explanations to the student's level
- Use real-world analogies to make concepts relatable

When a student needs help:
1. First understand what they're asking — identify the exact subject and topic correctly
2. Use the appropriate tool to provide structured guidance
3. Always provide the actual answer along with the explanation

Available tools:
- generate_practice_problems: Create practice exercises
- explain_concept: Give tailored explanations
- check_solution: Evaluate student work with constructive feedback
- create_study_plan: Build personalized study schedules
- get_step_by_step_guidance: Walk through problems step by step""",
        tools=[
            generate_practice_problems,
            explain_concept,
            check_solution,
            create_study_plan,
            get_step_by_step_guidance,
        ],
    )
    return agent


async def analyze_image_with_agent(
    image_data: str,
    mime_type: str = "image/jpeg",
    question: str = "What do you see in this image? If it's homework or a problem, identify the subject and help the student.",
) -> str:
    """Use the ADK agent to analyze an uploaded image.

    Args:
        image_data: Base64-encoded image data.
        mime_type: MIME type of the image.
        question: Question to ask about the image.

    Returns:
        The agent's analysis and response.
    """
    try:
        if settings.google_api_key:
            client = genai.Client(api_key=settings.google_api_key)
        else:
            client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_region,
            )

        raw_image = base64.b64decode(image_data)

        response = await client.aio.models.generate_content(
            model=settings.gemini_vision_model,
            contents=[
                types.Content(
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                data=raw_image,
                                mime_type=mime_type,
                            )
                        ),
                        types.Part(text=question),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=TUTOR_ANALYSIS_INSTRUCTION,
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )

        return response.text or "I couldn't analyze the image. Could you try again with a clearer photo?"

    except Exception as e:
        logger.error(f"Error analyzing image: {e}")
        return f"I had trouble analyzing that image. Could you try taking a clearer photo? Error: {str(e)}"


TUTOR_ANALYSIS_INSTRUCTION = """You are an expert tutor analyzing a student's homework or study material.

When analyzing an image:
1. Identify the subject and specific topic
2. Read any problems, equations, or text visible
3. Note any work the student has already done
4. Identify any errors in the student's work (if present)
5. Provide step-by-step solutions with clear explanations and the final answer

Structure your response as:
- **Subject**: [identified subject]
- **Topic**: [specific topic]
- **What I see**: [description of the content]
- **Your work so far**: [assessment of any existing work]
- **Solution**: [step-by-step walkthrough with the final answer]

Be encouraging and patient. Explain each step clearly so the student understands the reasoning."""
