"""Demo content for `manage.py seed_demo`: the UAP CSE course list and a set of sample notes.

Courses: BSc in CSE, University of Asia Pacific, as listed at https://cse.uap-bd.edu/academics/courses/
(code, title, credit hours, year, semester, theory or lab). Only the title is stored as the course; the
code, year and semester go on each note, as when a student uploads one.

People in the demo are made up. Their passwords never live here: see the command's --demo-password.
"""

UNIVERSITY = 'UAP'
DEPARTMENT = 'Computer Science and Engineering'
COURSES_SOURCE = 'https://cse.uap-bd.edu/academics/courses/'

# (code, title, credits, year, semester, kind)
COURSES = [
    ('CSE 101', 'Computer Fundamentals and Programming', 3.0, 1, 1, 'Theory'),
    ('CSE 102', 'Computer Fundamentals and Programming Lab', 1.5, 1, 1, 'Lab'),
    ('ENG 101', 'English', 3.0, 1, 1, 'Theory'),
    ('HSS 111', 'Bangladesh Studies: History, Society, and Culture', 3.0, 1, 1, 'Theory'),
    ('MTH 101', 'Math-I: Calculus I', 3.0, 1, 1, 'Theory'),
    ('PHY 101', 'Physics for Computer Science', 3.0, 1, 1, 'Theory'),
    ('PHY 102', 'Physics for Computer Science Lab', 1.5, 1, 1, 'Lab'),
    ('CHM 111', 'Chemistry', 3.0, 1, 2, 'Theory'),
    ('CSE 103', 'Structured Programming', 3.0, 1, 2, 'Theory'),
    ('CSE 104', 'Structured Programming Lab', 1.5, 1, 2, 'Lab'),
    ('CSE 105', 'Discrete Mathematics', 3.0, 1, 2, 'Theory'),
    ('CSE 108', 'Competitive Programming', 1.5, 1, 2, 'Lab'),
    ('EEE 101', 'Electrical Circuits', 3.0, 1, 2, 'Theory'),
    ('EEE 102', 'Electrical and Electronic Engineering I Lab', 3.0, 1, 2, 'Lab'),
    ('MTH 103', 'Math-II: Calculus II', 3.0, 1, 2, 'Theory'),
    ('CSE 201', 'Object-Oriented Programming I', 3.0, 2, 1, 'Theory'),
    ('CSE 202', 'Object-Oriented Programming I Lab', 1.5, 2, 1, 'Lab'),
    ('CSE 203', 'Data Structures and Algorithms I', 3.0, 2, 1, 'Theory'),
    ('CSE 204', 'Data Structures and Algorithms Lab I', 1.5, 2, 1, 'Lab'),
    ('CSE 205', 'ICT Law, Policy, and Ethics', 3.0, 2, 1, 'Theory'),
    ('EEE 201', 'Electronic Devices and Circuits', 3.0, 2, 1, 'Theory'),
    ('EEE 202', 'Electronic Devices and Circuits Lab', 1.5, 2, 1, 'Lab'),
    ('MTH 201', 'Math III: Vector Geometry and Linear Algebra', 3.0, 2, 1, 'Theory'),
    ('CSE 207', 'Data Structures and Algorithms II', 3.0, 2, 2, 'Theory'),
    ('CSE 208', 'Data Structures and Algorithms II Lab', 1.5, 2, 2, 'Lab'),
    ('CSE 209', 'Digital Logic Design', 3.0, 2, 2, 'Theory'),
    ('CSE 210', 'Digital Logic Design Lab', 1.5, 2, 2, 'Lab'),
    ('CSE 211', 'Database Systems', 3.0, 2, 2, 'Theory'),
    ('CSE 212', 'Database Systems Lab', 1.5, 2, 2, 'Lab'),
    ('ECN 201', 'Engineering Economics', 3.0, 2, 2, 'Theory'),
    ('MTH 203', 'Math-IV: Probability and Statistics', 3.0, 2, 2, 'Theory'),
    ('BIE 301', 'Bioinformatics Engineering', 3.0, 3, 1, 'Theory'),
    ('BUS 301', 'Business and Entrepreneurship', 3.0, 3, 1, 'Theory'),
    ('CSE 301', 'Object Oriented Programming II: Visual and Web Programming', 3.0, 3, 1, 'Theory'),
    ('CSE 302', 'Object Oriented Programming II: Visual and Web Programming Lab', 1.5, 3, 1, 'Lab'),
    ('CSE 303', 'Computer Architecture', 3.0, 3, 1, 'Theory'),
    ('CSE 305', 'Systems Analysis and Design', 3.0, 3, 1, 'Theory'),
    ('CSE 307', 'Project Management and Strategy', 0.0, 3, 1, 'Theory'),
    ('ENG 300', 'Technical Writing and Presentation', 1.5, 3, 1, 'Theory'),
    ('CSE 311', 'Data Communication and Computer Networks', 3.0, 3, 2, 'Theory'),
    ('CSE 312', 'Data Communication and Computer Networks Lab', 1.5, 3, 2, 'Lab'),
    ('CSE 313', 'Software Engineering', 3.0, 3, 2, 'Theory'),
    ('CSE 314', 'Software Engineering Lab', 1.5, 3, 2, 'Lab'),
    ('CSE 315', 'Microprocessors and Microcontrollers', 3.0, 3, 2, 'Theory'),
    ('CSE 316', 'Microprocessors and Microcontrollers Lab', 1.5, 3, 2, 'Lab'),
    ('CSE 317', 'Computer and Cyber Security', 3.0, 3, 2, 'Theory'),
    ('CSE 402', 'Operating System Lab', 1.5, 3, 2, 'Lab'),
    ('PHY 301', 'Modern and Quantum Physics', 3.0, 3, 2, 'Theory'),
    ('CSE 401', 'Operating System', 3.0, 4, 1, 'Theory'),
    ('CSE 405', 'Numerical and Mathematical Analysis for Engineers', 3.0, 4, 1, 'Theory'),
    ('CSE 413', 'Machine Learning and Deep Learning', 3.0, 4, 1, 'Theory'),
    ('CSE 414', 'Machine Learning and Deep Learning Lab', 1.5, 4, 1, 'Lab'),
    ('CSE 437', 'Robotics', 3.0, 4, 1, 'Theory'),
    ('CSE 438', 'Robotics Lab', 1.5, 4, 1, 'Lab'),
    ('IMG 401', 'Industry and Operational Management', 3.0, 4, 1, 'Theory'),
    ('CSE 425', 'Computer Graphics', 3.0, 4, 2, 'Theory'),
    ('CSE 426', 'Computer Graphics Lab', 1.5, 4, 2, 'Lab'),
    ('CSE 429', 'Compiler Design', 3.0, 4, 2, 'Theory'),
    ('CSE 430', 'Compiler Design Lab', 1.5, 4, 2, 'Lab'),
]

# Demo accounts (all made up). key -> account details. Every account gets a verified email.
ACCOUNTS = {
    'moderator': {'username': 'demo_moderator', 'first_name': 'Nusrat', 'last_name': 'Jahan',
                  'user_type': 'moderator', 'gender': 'Female'},
    'provider': {'username': 'demo_provider', 'first_name': 'Arif', 'last_name': 'Hasan',
                 'user_type': 'provider', 'gender': 'Male'},
    'provider2': {'username': 'demo_provider2', 'first_name': 'Tasnim', 'last_name': 'Ahmed',
                  'user_type': 'provider', 'gender': 'Female'},
    'provider3': {'username': 'demo_provider3', 'first_name': 'Rakib', 'last_name': 'Chowdhury',
                  'user_type': 'provider', 'gender': 'Male'},
    'basic': {'username': 'demo_basic', 'first_name': 'Sadia', 'last_name': 'Karim',
              'user_type': 'basic', 'gender': 'Female'},
    'premium': {'username': 'demo_premium', 'first_name': 'Imran', 'last_name': 'Kabir',
                'user_type': 'basic', 'gender': 'Male'},
}

# (name, description, price in taka, months)
PREMIUM_PACKAGES = [
    ('Monthly', 'Send your problems to providers through NoteSolve for one month.', 99, 1),
    ('Semester', 'Four months of NoteSolve: enough for one full semester.', 349, 4),
    ('Yearly', 'A whole year of NoteSolve at the best price.', 899, 12),
]

# Sample notes: (course code, provider key, title, published?, days ago, sections).
# Each section is (heading, [points]); the command turns them into a PDF.
NOTES = [
    ('CSE 101', 'provider', 'Intro to Programming in C: Lecture Notes', True, 60, [
        ('Computer basics', ['Hardware, software and the operating system',
                             'Number systems: binary, octal, decimal, hexadecimal and conversions',
                             'How a program is compiled and run']),
        ('C language basics', ['Variables, data types and constants', 'Arithmetic, relational and logical operators',
                               'Input and output with printf and scanf']),
        ('Control flow', ['if, else if, else and switch', 'for, while and do-while loops',
                          'break and continue with examples']),
        ('Functions', ['Declaring and defining functions', 'Parameters and return values',
                       'Scope of variables']),
    ]),
    ('MTH 101', 'provider2', 'Calculus I: Limits, Derivatives and Their Uses', True, 55, [
        ('Limits and continuity', ['Limit of a function, one-sided limits', 'Limit laws and standard limits',
                                   'Continuity and types of discontinuity']),
        ('Differentiation', ['Derivative from first principles', 'Product, quotient and chain rules',
                             'Derivatives of trigonometric, exponential and log functions']),
        ('Applications', ["Rolle's theorem and the mean value theorem", 'Maxima and minima',
                          "Indeterminate forms and L'Hopital's rule"]),
    ]),
    ('PHY 101', 'provider3', 'Physics for CS: Mid-term Notes', True, 52, [
        ('Mechanics', ['Vectors and their components', 'Motion in one and two dimensions',
                       "Newton's laws of motion", 'Work, energy and power']),
        ('Electricity', ["Charge and Coulomb's law", 'Electric field and potential',
                         "Current, resistance and Ohm's law"]),
    ]),
    ('CSE 103', 'provider', 'Arrays, Strings and Pointers in C', True, 45, [
        ('Arrays', ['One and two dimensional arrays', 'Passing arrays to functions', 'Searching an array']),
        ('Strings', ['Character arrays and the null terminator', 'strlen, strcpy, strcmp and strcat',
                     'Reading a line of text safely']),
        ('Pointers', ['Address-of and dereference operators', 'Pointer arithmetic and arrays',
                      'Call by reference with pointers']),
        ('Structures and files', ['Defining and using struct', 'Arrays of structures',
                                  'Reading and writing files with fopen, fprintf and fscanf']),
    ]),
    ('CSE 105', 'provider2', 'Discrete Mathematics: From Logic to Graphs', True, 44, [
        ('Logic', ['Propositions, connectives and truth tables', 'Logical equivalence and laws',
                   'Predicates and quantifiers']),
        ('Sets, relations and functions', ['Set operations and Venn diagrams',
                                           'Properties of relations: reflexive, symmetric, transitive',
                                           'Injective, surjective and bijective functions']),
        ('Proofs and counting', ['Direct proof, contradiction and induction', 'Permutations and combinations',
                                 'The pigeonhole principle']),
        ('Graphs and trees', ['Graph terms, degree and paths', 'Euler and Hamilton paths',
                              'Trees and spanning trees']),
    ]),
    ('CSE 105', 'provider3', 'Discrete Mathematics: Solved Final Questions', True, 30, [
        ('How to use this note', ['Each topic has two solved past-style questions',
                                  'Try the question first, then compare with the answer']),
        ('Solved problems', ['Truth table and equivalence proofs', 'Proof by induction: sums and divisibility',
                             'Counting problems with repetition', 'Finding Euler circuits in a graph']),
    ]),
    ('CSE 201', 'provider', 'Java OOP: Classes to Interfaces', True, 40, [
        ('Classes and objects', ['Fields, methods and constructors', 'The this keyword',
                                 'Static members']),
        ('The four pillars', ['Encapsulation with private fields and getters', 'Inheritance and super',
                              'Method overriding and polymorphism', 'Abstraction with abstract classes']),
        ('Interfaces and exceptions', ['Defining and implementing interfaces', 'try, catch and finally',
                                       'Writing your own exception class']),
    ]),
    ('CSE 203', 'provider2', 'Data Structures and Algorithms I: Full Notes', True, 38, [
        ('Analysing algorithms', ['Time and space complexity', 'Big-O, Big-Omega and Big-Theta']),
        ('Linear structures', ['Arrays and linked lists (single, double, circular)',
                               'Stacks: push, pop and uses', 'Queues and circular queues']),
        ('Recursion', ['Base case and recursive case', 'Recursion tree', 'Tower of Hanoi']),
        ('Sorting and searching', ['Bubble, selection and insertion sort', 'Merge sort and quick sort',
                                   'Binary search']),
    ]),
    ('CSE 204', 'provider', 'DSA Lab I: Solved Lab Tasks', True, 35, [
        ('Lab tasks', ['Linked list: insert, delete and reverse', 'Stack using an array and a linked list',
                       'Balanced brackets with a stack', 'Queue simulation',
                       'Merge sort and quick sort with step counts']),
    ]),
    ('MTH 201', 'provider3', 'Vectors, Matrices and Linear Systems', True, 33, [
        ('Vector geometry', ['Dot and cross product', 'Lines and planes in space']),
        ('Matrices', ['Matrix operations and inverse', 'Determinants and their properties']),
        ('Linear systems', ['Gaussian and Gauss-Jordan elimination', 'Rank and consistency']),
        ('Vector spaces', ['Subspaces, span and linear independence', 'Basis and dimension',
                           'Eigenvalues and eigenvectors']),
    ]),
    ('CSE 207', 'provider2', 'Graph Algorithms and Dynamic Programming', True, 28, [
        ('Graph search', ['Graph representations', 'Breadth-first and depth-first search',
                          'Topological sort']),
        ('Shortest paths and trees', ["Dijkstra's algorithm", 'Bellman-Ford', "Kruskal's and Prim's MST"]),
        ('Design techniques', ['Greedy algorithms: activity selection', 'Dynamic programming: 0/1 knapsack',
                               'Longest common subsequence']),
    ]),
    ('CSE 209', 'provider3', 'Digital Logic Design: Gates to Counters', True, 26, [
        ('Boolean algebra', ['Logic gates and truth tables', 'Boolean laws and simplification',
                             'Karnaugh maps']),
        ('Combinational circuits', ['Half and full adders', 'Multiplexers and decoders', 'Comparators']),
        ('Sequential circuits', ['SR, D, JK and T flip-flops', 'Registers and shift registers',
                                 'Synchronous and asynchronous counters']),
    ]),
    ('CSE 211', 'provider', 'Database Systems: ER Model, SQL and Normalization', True, 24, [
        ('Modelling', ['Entities, attributes and relationships', 'ER diagrams to tables',
                       'Keys: primary, candidate and foreign']),
        ('SQL', ['CREATE, INSERT, UPDATE and DELETE', 'SELECT with joins', 'GROUP BY, HAVING and subqueries']),
        ('Design and transactions', ['Functional dependencies', 'Normal forms: 1NF, 2NF, 3NF and BCNF',
                                     'Transactions and ACID']),
    ]),
    ('CSE 212', 'provider', 'SQL Lab Sheet with Answers', True, 20, [
        ('Lab queries', ['Create a university database', 'Find students by department and CGPA',
                         'Join courses, teachers and enrolments', 'Count students per course',
                         'Create a view and an index']),
    ]),
    ('MTH 203', 'provider2', 'Probability and Statistics: Formula Sheet and Examples', True, 18, [
        ('Probability', ['Sample space and events', "Conditional probability and Bayes' theorem"]),
        ('Distributions', ['Binomial and Poisson', 'Normal distribution and z-scores']),
        ('Statistics', ['Mean, median, variance', 'Correlation and linear regression']),
    ]),
    ('CSE 303', 'provider3', 'Computer Architecture: Pipelining and Memory', True, 16, [
        ('Instruction sets', ['Instruction formats and addressing modes', 'MIPS basics']),
        ('Pipelining', ['Five stage pipeline', 'Data, control and structural hazards', 'Forwarding and stalls']),
        ('Memory', ['Cache mapping: direct, associative, set-associative', 'Hit rate and average access time']),
    ]),
    ('CSE 311', 'provider2', 'Data Communication and Networks: Layer by Layer', True, 14, [
        ('Models', ['The OSI and TCP/IP models']),
        ('Lower layers', ['Signals, encoding and modulation', 'Framing and error detection with CRC']),
        ('Network and transport', ['IPv4 addressing and subnetting', 'Routing basics', 'TCP versus UDP']),
    ]),
    ('CSE 313', 'provider', 'Software Engineering: SDLC to Testing', True, 12, [
        ('Process', ['Waterfall, incremental and spiral models', 'Agile and Scrum']),
        ('Requirements and design', ['Functional and non-functional requirements', 'Use case and class diagrams',
                                     'Common design patterns']),
        ('Testing', ['Unit, integration and system testing', 'Black box and white box testing']),
    ]),
    ('CSE 317', 'provider3', 'Computer and Cyber Security Notes', True, 10, [
        ('Basics', ['Confidentiality, integrity and availability', 'Threats, vulnerabilities and risk']),
        ('Cryptography', ['Symmetric and public key encryption', 'Hashing and digital signatures']),
        ('Attacks and defences', ['SQL injection and cross-site scripting', 'Phishing and social engineering',
                                  'Firewalls and intrusion detection']),
    ]),
    ('CSE 401', 'provider2', 'Operating System: Processes to File Systems', True, 8, [
        ('Processes', ['Processes and threads', 'CPU scheduling: FCFS, SJF, Round Robin, priority']),
        ('Synchronization', ['Critical section problem', 'Semaphores and mutex locks',
                             'Deadlock and the banker\'s algorithm']),
        ('Memory and storage', ['Paging and segmentation', 'Virtual memory and page replacement',
                                'File system structure']),
    ]),
    ('CSE 413', 'provider', 'Machine Learning and Deep Learning: Core Ideas', True, 6, [
        ('Machine learning', ['Supervised and unsupervised learning', 'Linear and logistic regression',
                              'Decision trees and k-nearest neighbours', 'Accuracy, precision, recall and F1']),
        ('Deep learning', ['Neurons, layers and activation functions', 'Backpropagation and gradient descent',
                           'Convolutional neural networks']),
    ]),
    ('CSE 429', 'provider3', 'Compiler Design: Lexing, Parsing and Code', True, 4, [
        ('Front end', ['Phases of a compiler', 'Lexical analysis with regular expressions and DFAs',
                       'LL(1) and LR parsing']),
        ('Back end', ['Syntax-directed translation', 'Three-address code', 'Basic code optimisation']),
    ]),
    # Waiting for review: these fill the moderator's queue in the demo.
    ('CSE 425', 'provider2', 'Computer Graphics: Transformations and Clipping', False, 2, [
        ('Topics', ['Line drawing: DDA and Bresenham', '2D and 3D transformations', 'Clipping algorithms']),
    ]),
    ('CSE 315', 'provider', 'Microprocessors: 8086 Assembly Basics', False, 1, [
        ('Topics', ['8086 registers and memory segmentation', 'Addressing modes', 'Basic assembly programs']),
    ]),
    ('ENG 101', 'provider3', 'English: Paragraph and Essay Writing', False, 1, [
        ('Topics', ['Topic sentence and supporting details', 'Essay structure', 'Common grammar mistakes']),
    ]),
]

# (note title, reader key, stars, comment or '')
FEEDBACK = [
    ('Intro to Programming in C: Lecture Notes', 'basic', 5, 'Very clear. The loop examples helped a lot.'),
    ('Intro to Programming in C: Lecture Notes', 'premium', 4, ''),
    ('Data Structures and Algorithms I: Full Notes', 'basic', 5, 'Best DSA notes I have found, thank you!'),
    ('Data Structures and Algorithms I: Full Notes', 'premium', 5, ''),
    ('Data Structures and Algorithms I: Full Notes', 'provider', 4, ''),
    ('Database Systems: ER Model, SQL and Normalization', 'premium', 5,
     'The normalization part finally made sense to me.'),
    ('Database Systems: ER Model, SQL and Normalization', 'basic', 4, ''),
    ('Discrete Mathematics: From Logic to Graphs', 'basic', 4, 'Could you add a few more induction examples?'),
    ('Graph Algorithms and Dynamic Programming', 'premium', 5, ''),
    ('Digital Logic Design: Gates to Counters', 'basic', 4, ''),
    ('Operating System: Processes to File Systems', 'premium', 5, 'Saved me before the mid-term.'),
    ('Java OOP: Classes to Interfaces', 'premium', 4, ''),
    ('Computer and Cyber Security Notes', 'basic', 5, ''),
]
