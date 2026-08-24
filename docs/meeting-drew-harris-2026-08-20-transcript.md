# Meeting transcript — Drew Harris × Muhammad Atif

**Date:** Thursday, 20 Aug 2026 (approx.)  
**Context:** Follow-up — Overtone stack + Meet join demo; Expert Scale / Apex Replicant  
**Participants:** Drew Harris (Expert Scale), Muhammad Atif (Overtone)

---

## Transcript (as provided)

Automated note-taker that joins meetings and what technology are you using in that regard?

All right, that's great, by the way. So I will definitely keep the things tight and how the overall flow should happen, like how bot joins the room and how to stay grounded in our deck sessions, right, by the way. So, and where I would put upstream and escalations. So I will definitely, for that purpose, I can share the screen with you first so that you can get the idea about it.

That would be great. Yeah, go ahead.

Okay, so is it visible, right?

Yes.

Okay, so this is the main Presenter Operation Studio where basically the overall sessions you can see, and you can see the presentations, how much decks I, how much presentations I uploaded in this dashboard, right? You can set up the agents in this here from here. Like I can pick any agents and you can set the instructions, right? So this is the like a panel where I can just select the presentation slides or whatever the stuff, PDF. I can select it and it will start indexing in the backend systems in the RAG-based, in terms of RAG pipeline. And it will check, it will extract the metadata and then ground it into the vector database, right? pgvector I used for that. And then we can simply launch the meeting. Like, this is the meeting. I can just put the meeting here. So, and then I can select the present, uh, PPTX presentation slides just for knowledge base. And the other thing is I can just select these things. So I, when I connect the board, so we can see here, uh, just, just for a second.

Right, I see it was wanting to join. Yep, I, I can admit it for you.

I don't—

oh, there's 2 of them here. I'll admit them because I don't know that you can—

you can just give access one, one of them, uh, not the second one, uh, just one. Okay.

one. Okay.

All right, I'm gonna move one of them. There you go. Okay.

Okay, so hey, Overton, just a minute. Okay, so it's— I can just show you.

It looks like you stopped sharing your screen, by the way.

Yeah, just a minute. Just, I'm just—

OK.

Doing— basically, it's currently under active builds. So that's why I can just have it to— Okay, so this is the one guest. I got it. This is the second meeting. I just did it for just to give you the idea. Right. So this is how, uh, the, like, uh, the bot joins the meetings, right? So after that, when I ask anything, it can simply, uh, can navigate to that slide and then answer to from that deck.

Okay. Can you give me an example? Like, can you ask something and have it navigate for you? Yeah.

Yeah, just a minute because it usually— it is listening right now, and then when I stop, uh, speaking, then it can speak and then say about this thing. So, hey, Overton. All right, so can you, uh, please tell me about market opportunities in Frontier AI?

opportunities in Frontier AI?

Market opportunities. Oh, sorry, you're doing your slide thing. Okay, so just so you know, I'm not hearing whatever it's saying. The audio is not coming through. I think when you share, you have to allow it to share the audio from that particular tab.

So maybe you can just leave this overtone agent that you earlier gave access to. And then I can just again connect the bot and it will be here in this meeting. So that's what— then you will be able to see that.

Sounds good.

Can you remove this agent from here?

Let me remove it.

Remove.

Okay. Yep, removes.

You can give this— give access to this bot again. Okay. Is it sharing?

Yeah, yeah, there we go.

All right, so here, Overton, can you just tell me about market opportunities in Frontier AI and which slides discuss these scenarios? There. Okay, so are you— can you hear me? Correctly, right? So—

Yes, I hear you. Yep.

Okay, so the thing is, uh, there might be an issue. I was just testing, uh, before, uh, our meeting, by the way. So the thing is, uh, usually you can, uh, you can kick these, uh, agents from the meeting for now. I can just discuss with this, with this thing with you and the architectures, what, uh, what was discussed, what was designed for this.

Right. So yeah, tell me a little bit more about what do you use to allow it to connect to the meeting? What is the underlying protocol or architecture in regards?

So basically, mainly the Recall AI, these platforms is a meeting recording and this gives the access to a bot to join the meeting. So this is the platform basically mainly we called, and this is the layers. I can just discuss this thing with you. The thing is like when that's the main system context about human operates, and usually the backend is designed in a way like when basically there is a— We have this platform, this access and Overton.

Uh-huh.

Overton dashboard, over— and that, that is the main platforms. Uh, might be I'm missing something. So console.api.

How long have you been working on this?

Yeah, can you repeat?

Yeah, how long have you been developing this solution?

Basically, uh, around 3 weeks. Uh, from the last 3 weeks we were working on this, and the overall setup was designed— basically, I searched the architecture designs about RAG pipelines. That's why I just Reach out. I would just check your platforms and replicate how you currently zero hallucinations. And then, so that's the main thing I was just checking. So these are the all endpoints that is designed behind the, behind the scene, like the how agents call and the how agents works and bot design, how bot handle customer queries. Right? So join the meetings and then leave the meeting and everything there. Admin, how admin handle everything in this dashboard, right? So I just, I enter the Google Meet link and select the present knowledge base. And then I just select the auto presentation, right? So this is like when I, here, this is the things like the main context of agents. I just give default. And then connect the bots. So it has, it has the three things in common, right? So first one is like it has the presentations like PPTX where that is indexed into into the vector database. Like firstly when we upload the presentations PPTX, then it can extract every page information. JSON format, right? Like Google Visions models we used, like that can capture the screenshots or whatever in that specific page of PPTX, right? So once it can capture that information, it's stored in JSON format. Like you can say, okay, Okay, so it can— it creates— there might be a bunch of— right, so in this format it's stores the data, like what is the file names, either that is ready or not, either what is their ID and everything, how much chunks of that is created and meta models, all the stuffs and in multiple files. Once it has everything, then in index.json files, it can store all the information about each slides. And so that when we say navigate to slide number 5, it can navigate to that slide and then explain that specific slides to the other person. Right. So index.json file store all that and meta.json file, it specifically have the context about the slide page numbers and the specific name of that files. Right. So that's it. Create automatically everything, right? We just have to upload the PDF and PPTX is here and it can upload to vector DBs as a vector store and also the file into the GCS buckets in Google Cloud Platform, Google Cloud Run, Cloud Platform, right? So it can store the knowledge base in vector DBs and Google Cloud Platform. And then when we select any specific— that's why when I was here launching, I just select that specific knowledge base, right? I select that knowledge base and then launch the agents in the specific meeting. So that agents will come into the meeting and then explain that specific slides to us. Whatever we will ask questions, it can navigate to the specific slides and then respond to us. Right. So the Google Live Speech-to-Speech Conversion APIs we used behind the scenes. And also that is the architectures, by the way, like real-time voice Gemini Live APIs we use, slide index, pgvector we use, and Recall API. Recall AI, that is basically meeting joining bot. So that's the main stuff. And post-session. So this is the system, main system context, how the requests are handling. I will definitely share this with you too about, uh, the whole flow later on.

Yeah, that'd be great. I appreciate that.

Yeah.

What, what is your market? Are you looking to develop this as a product and sell it?

And so basically the thing is, uh, we started this project as a, uh, to, uh, to market later on. Definitely in this month we have to complete this product, like at the end of August, and then from the, from the start of next month we will definitely start a GTM. On this, and we were just confirming everything regarding like what, how we can add guardrails in, in the specific edge cases so that this will handle all the scenarios. Currently, you, you are— you can also test this platform after this meeting. It will definitely work fine when you test this. I will share the URL with you too. Right. So the thing is, you can test these platforms, and definitely we will. We are concreting the architecture of this, and then later on. Okay, I have shared the link with you too. After this meeting, you can just test it a bit, and then you will you will see we we have to we. definitely have to resolve the latency issues. Like latency, it is taking a bit of time, like 3 to 4 seconds to respond back to the user. So definitely we have to resolve that too. But the main thing is the grounding thing, like how the voice APIs can respond and talk to the persons and can answer the queries.

Got it. That makes sense. Very cool. Well, I really appreciate the demonstration, and I look forward to getting all those links from you and learning a little bit more as I dig in.

Yeah. So in— I would say the high-level architecture is like the Recall join as a participant and open a presentation page as a board camera, right? So then mic audio goes to the real-time speech-to-speech models. like Google Gemini Live, we used basically for speech-to-speech convergence through our backend relay. And then tool calls on the backend navigate, get slide details, and search the indexed deck, right? So that the return slides can be represented to the user.

Okay.

Okay.

So that's the main thing. And the vision models extract or page text. and then we embed into the vector database. That's the main scenarios we basically handle in this overall system.

Okay, I really appreciate it. This has been very educational. I look forward to digging in a little bit more.

Yeah, so definitely. And the other thing is If it's useful, definitely we have to see which and like how the like I can say in simple words. Just a minute. So basically, one more thing I was just checking in my documents, that is basically on guardrails. Our mapping, our main mappings, that's the main things I want to discuss with you.

Okay.

The thing is, the thing is what we have designed, designed like the context sufficiency and back you ask should clarify before answering. That's the main thing we, we were definitely looking and we have to resolve in this overall system and the sourcing first and escalate if we can't ground it, we should hand it to the human expert and treat that answer as ground truth. So that's also, we want to integrate that. But for that things, I definitely, I want to ask you like what specific scenarios you have used for such purpose in Protege? Like how the sessions should be treated as, should be handled and escalated to the human expert? Rather than the voice agents can respond to that queries?

Yeah, so the times that it escalates are when it doesn't have enough information to answer. That's the biggest opportunity. So if it gets asked a question that it just doesn't know the answer to, it defers to the experts. And that happens when something is out of context. So for instance, if somebody is working with a protégé that is specialized in go-to-market strategy, and that's the area of expertise, and the person that's talking to that protégé asks about something totally different like manufacturing best practices, it's not going to know the answer to that. So it's going to say, hey, that's outside of the scope. But then if it's something about go-to-market strategy, which is on scope, on target, but it doesn't have enough context or enough information to answer, it'll try to get the additional context that it needs to dig deeper and find the information in the knowledge base. And then if it still can't find it, then it'll escalate to the human. There is one more scenario that we typically see where it escalates to the human, and that's in, in a new line of products that we're offering for lead generation. So we will offer a version of a protégé, like a consultant protégé, for an expert to use, like on their web page. And the client can interact with that, but in a limited capacity. And the protégé is directed to escalate more serious queries or time commitments to the expert to try to drive the client to book time with the actual expert. So that's a completely different use case. Yeah.

So that's, by the way, the main things. The thing is that maps cleanly out of scope, refuse on scope, dig the knowledge base, and then escalate to the human if it's still thin. So the thing is, if it's useful, I would propose a short spike like meeting join plus grounded answer plus an escalate stuff that logs need experts that The way your loop does, right? So who on your sides would own that conversation?

Uh, so I'm the architect and I have all that information, right? It'd be me.

Okay, so, uh, and where— by the way, uh, the thing is, uh, where I see fit in your Prodigies judgments layer plus our meeting join path. So in On live call, it can follow that same escalated letter, right? So including your consultations, uh, lead gen, and limited capacity case, if you ever put that in Zoom or meeting.

Yes, yes. Um, right now everything is done through a web interface and it's not on a live meeting. So that's the missing piece that I was looking for, and I appreciate you sharing that with me of how you connect it with the live meeting. That's helpful.

Yeah, you can definitely, uh, uh, test it a bit. And definitely, definitely we are improving these, uh, platforms. And we— I'm also looking for the right shape, like the design partners and integration stacks, or the later on the capital scenarios, capital, and whichever actually helps experts scale, ship Google's Meet and Protégé. Uh, curious, by the way, which one of those, uh, is even on the table for you?

Which one of what is on the table for me?

Like, uh, okay, okay.

Yeah, the relationships. Go ahead and tell me what they were again. Uh, that, like, the design partners and integration stacks, or I would say collaboration partners is probably the best fit here for what you're doing and what we're doing. We find ways that we can work together and integrate our solutions with one another and maybe even just help each other out from time to time from an engineering perspective.

All right. Uh, so definitely we can, um, the best step I think is a short partnerships, uh, spike, right? So, and the collaboration spike, uh, where your existing escalation knowledge flow into the live meeting, uh, joins. We can definitely prove that, uh, it wants at least one end-to-end, then decide commercial shape, right? So, uh, do you want me to send a one-page spike outlines after this call?

Sure, you can do that. I'll take a look.

All right, so definitely I will share that with you. And then, uh, and in the meantime, you can have, uh, at least you can create your own Google Meet and then call— then give the Google Meet link to that, uh, dashboard I provided you in the Launch tab, and then at least have conversations with it. So that we can now, uh, a bit, uh, you can give us the feedback and then we can definitely have a conversation on that too so that we can improve these platforms in a grounded way so that we can represent these platforms too and integrate the layers in Protege if later on we can definitely go into that path.

---

## Related docs

- Architecture: [overtone-architecture-for-partners.md](./overtone-architecture-for-partners.md)
- Talk track: [drew-harris-15min-talk-track.md](./drew-harris-15min-talk-track.md)
