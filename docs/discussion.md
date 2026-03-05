The goal of the Nobious AI Module is allow the user to ask questions of the system in plain language.

 

This means the AI is being used primarily to generate the SQL needed to find the answer to their question.

 

I anticipate common questions to be:

 

Have I received any new materials recently for the Johnson High School job?
How many #1 filters do we have in stock and where are they located?
 

I see the AI eventually working in three categories:

 

Answering specific questions with text based answers.
Creating tabular report outputs in excel or .csv format based on queries.
An expert on the Nobious system to answer questions such as “In Nobious, how do it…”
 

Context and Training

I see context information and training coming from a few different sources:

Answering specific questions with text based answers.
Prior questions within the current session.
                                                              i.      Would be nice to store all historical questions but that might be too much for an initial phase.

We have already built a context application that can built a JSON context file based on relationships we define within the GUI.  It allows us to specify things like tables relationships.  We can also provide it example queries and associate those queries to key terms and tags.  I’m not sure how useful this app is now that we plan to place our AI on top of the API which has the relationships already defined.  But I wanted to mention this app in case it was useful.
Creating tabular report outputs in excel or .csv format based on queries.
An expert on the Nobious system to answer questions such as “In Nobious, how do it…”


Thanks Jason, for contacting me.

 -----------

I have a few questions.

1. Who is this user, is he someone from the customer service team and he wants to get details about the material they have received from some source ?  [JP] A user is one of our customers who wants information about their operations.

2. Are we trying to build a chat client which talks to our system to answer these questions or are we trying to build a system with which clients can integrate their own chat clients and use it the way they want or both ?  [JP] We only want to create a chat bot which talks to our system and to the user to answer questions.  Our customers do not typically have technical staff and will not be integrating.

3. If we are building a chat client, how is the user going to access it, from web browser/mobile/both ?  [JP] We have already built a User Interface in our mobile app where a user can tap a button to ask a question.  The question box is overlayed over the application.  They can type in their question or use the Microphone to ask a question.  Then UI then queries the API for a response.

 

I might have more questions once you provide answers to the above questions. Once I have a clear picture of the requirements, I will be able to provide you a clear idea of the solution and based on it will build the final thing, hope that makes sense.