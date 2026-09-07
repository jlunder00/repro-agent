
Capstone Project Proposal Template
Length: 1 to 2 pages. This is an individual proposal. Each student should propose their own problem and submit their own runnable baseline.

Basic Information

Field
Response
Student name

Project title

Repository / notebook link

Configuration location
Example: examples/readme.md

Section 1. Problem Definition
Define the problem clearly enough that another person can tell whether the system succeeds or fails.
For example:
What task your agent or system is trying to solve
Who the intended user is and what situation they are in
What the input is
What the output should be
What counts as success and what counts as failure
Avoid vague goals such as "make an agent better." State the task in operational terms.

Section 2. Motivation and Project Scope
Explain why this problem is worth solving and why it is feasible for a semester capstone project.
For example:
Why the problem matters
Why an agentic AI system is a reasonable approach
What you will include in scope this semester
What you will intentionally leave out of scope
A good scope is specific. It should be small enough to build and evaluate, but meaningful enough to improve over the baseline.

Section 3. Runnable Baseline
Describe the minimal system you built for this proposal. The baseline can be simple, but it must actually run.
Your baseline may be:
A single-call model baseline
A simple RAG baseline
A tool-use or workflow baseline
A rule-based baseline
A wrapper around an existing open-source system or API
Required explanation:
What model, tool, framework, or library the baseline uses
What the baseline does step by step
Why this is a reasonable starting point
What files or notebooks contain the baseline implementation

Section 4. Test Case and Baseline Output
Provide at least one concrete test case and the actual output produced by your baseline.
Include:
Sample input
Expected behavior or expected output
Actual baseline output (screenshot)
A short explanation of what worked and what did not work
The test case can be small. The goal is to show that the baseline is runnable and testable, not that it already solves the full project.

Section 5. Reproducibility and Run Instructions
Write instructions clear enough that the other students can run your baseline in a reasonable amount of time.
For example:
Dependencies and installation steps
Required API keys or environment variables, if any
The exact command or notebook cell used to run the baseline
Where the input file is located
Where the output appears
Any known setup limitations
Example command:
python run_baseline.py --input examples/test1.txt

Section 6. Initial Evaluation Plan
Describe how you will compare your future improved system against this baseline.
Possible evaluation criteria:
Task completion
Accuracy or correctness
Completeness of the output
Factuality
Cost
Latency
Tool failure rate
Safety or reliability
Human preference or LLM-as-a-judge rating
You do not need a full evaluation harness yet, but you should explain what evidence would show that your later system improves over the baseline.

Section 7. Limitations and Next Steps
Reflect on what the baseline cannot do yet and what you plan to improve next.
For example:
Known weaknesses of the current baseline
Failure cases you expect
What you will build in the next project phase
What risks might make the project difficult
What help, data, or infrastructure you may need


Grading
Section
Points
1. Problem Definition
15
2. Motivation and Project Scope
15
3. Runnable Baseline
25
4. Test Case and Baseline Output
25
5. Reproducibility and Run Instructions
10
6. Initial Evaluation Plan
5
7. Limitations and Next Steps
5
Total: 100 points.
Minimum baseline requirement: the baseline does not need to be strong, but it must be runnable, reproducible, and testable on at least one concrete example.

