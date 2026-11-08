"""Shared tiered questions and output-based validation for all game clients."""
import random
from campaign_questions import TIERS, problem
from runner import execute


def build_questions(language):
    return [[problem(language, topic, 'Debug', random.Random(topic))
             for topic in tier] for tier in TIERS]


def normalize(code):
    return ''.join(code.split())


def check_answer(submitted, question, language='Python'):
    reference = execute(question['answer'], language)
    result = execute(submitted, language)
    return (not reference['error'] and not result['error']
            and result['out'].strip() == reference['out'].strip())


def pick_questions(language, level, count, rng=None):
    rng = rng or random
    topics = []
    while len(topics) < count:
        topics.extend(rng.sample(TIERS[level], min(count-len(topics), len(TIERS[level]))))
    return [problem(language, topic, 'Debug', rng) for topic in topics]
