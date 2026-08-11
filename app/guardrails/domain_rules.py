"""Deployment-specific scope. Edit settings.guardrail_domain to re-scope
this system for a new project. Off-topic example phrases can also be
adjusted here if domain-adjacent terms cause false positives.
"""

from app.config.settings import settings

DOMAIN_NAME = settings.project_domain

DOMAIN_COLANG_TEMPLATE = """
define user ask off topic
  "tell me a joke"
  "what is the capital of france"
  "what is the capital of texas"
  "write me a poem"
  "what is 2 plus 2"
  "what should I eat for dinner"
  "who won the game yesterday"
  "recommend a movie"
  "what is the weather today"
  "can you help me with math homework"
  "tell me about world history"
  "what is the best restaurant near me"

define bot refuse off topic
  "I'm an Enterprise IT Assistant focused on {domain}. I can't help with that — but ask me anything technical!"

define flow handle off topic
  user ask off topic
  bot refuse off topic


define user express greeting
  "hello"
  "hi"
  "hey"
  "good morning"
  "good afternoon"
  "what's up"
  "howdy"

define bot express greeting
  "Hello! I'm your Enterprise IT Assistant. I specialise in {domain}. What can I help you with today?"

define flow greeting
  user express greeting
  bot express greeting


define user ask capabilities
  "what can you do"
  "what do you know"
  "help"
  "what are you"
  "what topics do you cover"
  "what can I ask you"
  "what are your capabilities"
  "what technical things can you help me with"
  "what kind of technical questions can you answer"
  "in what technical areas can you assist me"
  "what subjects can you assist with"
  "what can you help me with"

define bot explain capabilities
  "I'm an Enterprise AI Assistant with deep expertise in {domain}. Ask me anything in these areas!"

define flow capabilities
  user ask capabilities
  bot explain capabilities


define user express farewell
  "bye"
  "goodbye"
  "see you"
  "thanks bye"
  "that is all"
  "I am done"
  "see you later"

define bot express farewell
  "Goodbye! Feel free to return whenever you have more enterprise IT questions. Have a great day!"

define flow farewell
  user express farewell
  bot express farewell


define user express gratitude
  "thanks"
  "thank you"
  "appreciate it"
  "that helped"

define bot acknowledge gratitude
  "You're welcome! Let me know if you have any other {domain} questions."

define flow gratitude
  user express gratitude
  bot acknowledge gratitude
"""
