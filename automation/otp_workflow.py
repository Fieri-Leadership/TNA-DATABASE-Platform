import sys, os
sys.path.append(os.path.dirname(__file__))


from typing import TypedDict,List,Any
from datetime import datetime
from dataclasses import dataclass
from dotenv import load_dotenv
from logger import get_logger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage,HumanMessage
from langgraph.graph import StateGraph,START,END

from pydantic import BaseModel, Field
from document_fetch import generate_documents_from_db

load_dotenv()
logger = get_logger()
DATA_PATH = os.getenv("DATA_DIR")
ANALYSIS_LLM= "gemini-2.5-flash"
RECOMMENDER_LLM = "gpt-5.4-mini"
data_dict = None

## Langgraph Workflow Components
class Section(BaseModel):

    analysis:str = Field(
        description= "The generated analysis data in the form of facts, findings, claims, and other information for each given requirement. Generate clear pairs of <requirement,analysis> corresponding to each requirement. Do not make up the facts and only refer to the supplied input data. Make it formatted with markdown."
    )
    evidences: List[str]|None = Field(
        description= "The list of supporting evidence for the generated analysis for this item."
    )

analysis_llm = ChatGoogleGenerativeAI(
    model=ANALYSIS_LLM,
    temperature=0.3,
    max_tokens=5000,
    timeout=None,
    max_retries=2,
)

recommendation_llm = ChatOpenAI(
    model=RECOMMENDER_LLM,
    temperature=0.2,
    max_tokens=5000,
    timeout=None,
    max_retries=2,
)


@dataclass
class AnalysisInput:
    name:str
    description:str
    requirements:str
    input_data:str
    research_base_items: List[str]

@dataclass
class AnalysisSection:
    name:str
    input: AnalysisInput
    outcome: str
    evidences: List[str]

# LangGraph State
class AnalysisState(TypedDict):
    job_code:str
    completed_sections:List
    org_analysis_section: AnalysisSection
    needs_identification_section: AnalysisSection
    training_recommendations_section: AnalysisSection
       
analysis_sections_map = {"org_analysis": "Organisation Analysis",
                         "needs_identification": "Needs Identification",
                         "training_recommendations": "Training Recommendations"
                         }

# LLMs
analyser = analysis_llm.with_structured_output(Section)
recommender = recommendation_llm.with_structured_output(Section)


# Node 1- Organisational Analysis
def org_analysis(state:AnalysisState):
    if analysis_sections_map["org_analysis"] not in state["completed_sections"]:
        org_analysis_section:AnalysisSection = state["org_analysis_section"]
        org_analysis_input: AnalysisInput = org_analysis_section.input
        section:Section = analyser.invoke(
            [
                SystemMessage(content="You are a professional having tremendous amount of experience in the Human Learning and development domain. You are particularly skilled in analyzing organizational structures and development strategies. You always refer to the research base for evidence and justifications if available. Be concise, professional,objective and to the point."),
                HumanMessage(content=f"""
-> Task Instructions: Do a detailed Organisational analysis keeping the OTP model in mind for the given analysis requirements, providing evidence and/ justifications for the output. Be brief and to the point without adding extra unnecessary information. If you do not find anything that was asked in the requirements, you can leave that requirement output empty.

-> Analysis Task Description:
{org_analysis_input.description}                            

-> Analysis Requirements:
{org_analysis_input.requirements}

-> Analysis Resources:                            
***Input data***\n {org_analysis_input.input_data}

***Research base*** \n {org_analysis_input.research_base_items}

-> Your response:
"""
                )
            ]
        )
        org_analysis_section.outcome = section.analysis
        org_analysis_section.evidences = section.evidences
        # writer = get_stream_writer()
        # writer({"step_name":"Organisational Analysis","logging": f"Analysis:{section.analysis}"})
        # writer({"step_name":"Organisational Analysis","logging": f"Evidences:{section.evidences}"})
    
    return {"completed_state": "Organisation Analysis", 
            "org_analysis_section": org_analysis_section
                }

# Node 2- Needs Identification
def needs_identification(state:AnalysisState):
    if analysis_sections_map["needs_identification"] not in state["completed_sections"]:
        needs_id_section:AnalysisSection = state["needs_identification_section"]
        org_analysis_outcome = state["org_analysis_section"].outcome
        needs_id_input: AnalysisInput = needs_id_section.input
        section:Section = analyser.invoke(
            [
                SystemMessage(content="You are a professional having tremendous amount of experience in the Human Learning and development domain. You are particularly skilled in analyzing organizational structures and development strategies. You always refer to the research base for evidence and justifications if available. "),
                HumanMessage(content=f"""
-> Task Instructions: Do a detailed analysis for identifying the training needs the given analysis requirements, providing evidence and/ justifications for the output. Be brief and to the point without adding extra unnecessary information. If you do not find anything that was asked in the requirements, you can leave that requirement output empty.

-> Analysis Task Description:
{needs_id_input.description}                           

-> Analysis Requirements:
{needs_id_input.requirements}
                     
-> Analysis Resources:      
***Input data***\n 
1. Organisational analysis data: \n{org_analysis_outcome}

2. Learner Population data: \n{needs_id_input.input_data}

***Research base*** \n {needs_id_input.research_base_items}

-> Your Response:
""")]
        )
        needs_id_section.outcome = section.analysis
        needs_id_section.evidences = section.evidences
        # writer = get_stream_writer()
        # writer({"step_name":"Needs Identification","logging": f"Analysis:{section.analysis}"})
        # writer({"step_name":"Needs Identification","logging": f"Evidences:{section.evidences}"})
    return {"completed_state": "Needs Identification", 
            "needs_identification": needs_id_section
                }

# Node 3 - Training Recommendations
def training_recommendations(state:AnalysisState):
    if analysis_sections_map["training_recommendations"] not in state["completed_sections"]:
        training_rec_section:AnalysisSection = state["training_recommendations_section"]
        org_analysis_outcome = state["org_analysis_section"].outcome
        needs_id_outcome = state["needs_identification_section"].outcome
        training_rec_input: AnalysisInput = training_rec_section.input
        section:Section = analyser.invoke(
            [
                SystemMessage(content="You are a professional having tremendous amount of experience in the Human Learning and development domain. You are particularly skilled in analyzing organizational structures and development strategies. You always refer to the research base for evidence and justifications if available."),
                HumanMessage(content=f"""
-> Task Instructions: Consider all the data provided to you and draft a training recommendation interventions based on the given requirements, providing evidence and/ justifications for the output. Double check your recommendation for feasibility, ease of setup and effectiveness. Be brief and to the point without adding extra unnecessary information. If you do not find anything that was asked in the requirements, you can leave that requirement output empty.

-> Task Description:{training_rec_input.description}      

-> Task Requirements:{training_rec_input.requirements}

-> Available Resources:
***Input data***\n 
1. Organisational Analysis data**: \n{org_analysis_outcome}
2. Needs Identification data**: \n{needs_id_outcome}
3. Learner Population data**:\n{training_rec_input.input_data}

***Research base*** \n {training_rec_input.research_base_items}

-> Your Response:

""")]
        )
        training_rec_section.outcome = section.analysis
        training_rec_section.evidences = section.evidences
        # writer = get_stream_writer()
        # writer({"step_name":"Training Recommendations","logging": f"Analysis:{section.analysis}"})
        # writer({"step_name":"Training Recommendations","logging": f"Evidences:{section.evidences}"})
    return {"completed_state": "Training Recommendations", 
            "training_recommendations": training_rec_section
                }

## Common Utilities

def _prepare_and_compile_workflow_graph()->Any|None:
    # Analysis Subgraph builder
    analysis_subgraph_builder = StateGraph(AnalysisState)
    analysis_subgraph_builder.add_node("Organisational Analysis",org_analysis)
    analysis_subgraph_builder.add_node("Needs Identification",needs_identification)
    analysis_subgraph_builder.add_node("Training Recommendations",training_recommendations)
    analysis_subgraph_builder.add_edge(START,"Organisational Analysis")
    analysis_subgraph_builder.add_edge("Organisational Analysis","Needs Identification")
    analysis_subgraph_builder.add_edge("Needs Identification","Training Recommendations")
    analysis_subgraph_builder.add_edge("Training Recommendations",END)

    # Analysis subgraph workflow
    analysis_subgraph_workflow = analysis_subgraph_builder.compile()
    return analysis_subgraph_workflow
    # display(Image(analysis_subgraph_workflow.get_graph().draw_mermaid_png()))


# Data Ingestion layer replacement for now
def _make_data_md_files(job_code:str)->dict|None:
    """Function that generates the job data files for the given job code."""    
    input_data_path = f"{DATA_PATH}/{job_code}"
    generate_documents_from_db(job_code=job_code)
    client_input_data = None
    learner_input_data = None
    likert_input_data = None

    try:
        client_input_data = open(f"{input_data_path}/client_context_{job_code}.md", "r").read()
        learner_input_data = open(f"{input_data_path}/learner_context_{job_code}.md", "r").read()
        likert_input_data = open(f"{input_data_path}/likert_context_{job_code}.md", "r").read()
        logger.info(f"✓ Data fetch successful for job {job_code}.")
        data_dict = {
            "client_input_data": client_input_data,
            "learner_input_data": learner_input_data,
            "likert_input_data": likert_input_data

        }
        logger.debug(f"Data markdown files are successfully generated for job {job_code}.")
        return data_dict
    except FileNotFoundError as fe:
        logger.error(f"File not found: {repr(fe)}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {repr(e)}")
    return None


def _section_synthesiser(state:AnalysisState)->str|None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    job_code = state.get("job_code",None)

    if not job_code:
        logger.critical("LangGraph state processing error.: No job code found in the state.")
        return None
    else:
        input_data_path = f"{DATA_PATH}/{job_code}"
        intermediate_md_content =  f""" # Job Details: {state["job_code"]}
----------------------------------------------------------
# Organisation Analysis
## Analysis
{state["org_analysis_section"].outcome}
## Evidences
{state["org_analysis_section"].evidences}

# Identified Needs
## Analysis
{state["needs_identification_section"].outcome}
## Evidences
{state["needs_identification_section"].evidences}

# Training Recommendations
## Recommendations
{state["training_recommendations_section"].outcome}
## Evidences
{state["training_recommendations_section"].evidences}

----------------------------------------------------------"""
        path = os.path.join(input_data_path, f"{job_code}_Intermediate_analysis_report_{ts}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(intermediate_md_content)
        print(f"  ✓ File written {path}  ({len(intermediate_md_content):,} chars)")
        return intermediate_md_content

def execute_workflow(job_code:str)->str|None:
    data_dict = _make_data_md_files(job_code=job_code)
    try:
        if data_dict is None:
            raise ValueError("Failed to prepare graph data: Invalid data received.")
        else:
            org_analysis_input = AnalysisInput(
                name="Organisational Analysis",
                description="Generate a detailed analysis fulfilling following requirements.",
                requirements= """
- Short overview of the company to include size, sector, locations and recent developments
- Overview of strategy
- Overview of performance
- Details on identified knowledge/skills gap
- Key constraints, preferences and considerations including budget, numbers, languages and locations
- Required outcomes""",
                input_data= data_dict["client_input_data"],
                research_base_items=[]
            )
            org_analysis_section = AnalysisSection(name="Organisational Analysis", input=org_analysis_input, outcome="", evidences=[])


            needs_identification_input = AnalysisInput(
                name="Needs Identification",
                description="Identify the training needs based on the organisational analysis.",
                requirements= """- Find the priorities for organisations and training sponsors,  line-managers and the learner population and provide brief comment on similarities and differences.
- Find the strengths and weaknesses of the learner population based on the data collected and provide brief commentary.
- Link the Identified needs to organisational performance and strategy.""",
                input_data= data_dict["learner_input_data"],
                research_base_items=[]
            )
            needs_identification_section = AnalysisSection(name="Needs Identification", input=needs_identification_input, outcome="", evidences=[])


            needs_identification_input = AnalysisInput(
                name="Needs Identification",
                description="Identify the training needs based on the organisational analysis.",
                requirements= """- Find the priorities for organisations and training sponsors,  line-managers and the learner population and provide brief comment on similarities and differences.
- Find the strengths and weaknesses of the learner population based on the data collected and provide brief commentary.
- Link the Identified needs to organisational performance and strategy.""",
                input_data= data_dict["learner_input_data"],
                research_base_items=[]
            )
            needs_identification_section = AnalysisSection(name="Needs Identification", input=needs_identification_input, outcome="", evidences=[])

            training_recommendations_input = AnalysisInput(
                name="Training Recommendations",
                description="Provide training recommendations based on the organisational analysis and identified needs and other relevant information.",
                requirements= """- Identify the correct and the most appropriate delivery format based on client stipulations and learner preferences verified against relevant research.
- Look at the identified gaps and priorities relevant research to provide a recommended approach.
- Identify, include and define the key performance indicators (KPIs) to measure the effectiveness of the training.
- Reference relevant research to justify your recommended approach, and the benefits it could bring, potentially mapping against Kirkpatrick training evaluation model.""",
                input_data= data_dict["learner_input_data"],
                research_base_items=[]
            )
            training_recommendations_section = AnalysisSection(name="Training Recommendations", input=training_recommendations_input, outcome="", evidences=[])
            analysis_subgraph_workflow = _prepare_and_compile_workflow_graph()
            logger.debug("Completed compiling workflow.")
            logger.info("Running TNA workflow now.")
            state = analysis_subgraph_workflow.invoke({"job_code": job_code, 
                                            "completed_sections": [],  
                                            "org_analysis_section": org_analysis_section, 
                                            "needs_identification_section": needs_identification_section, 
                                            "training_recommendations_section": training_recommendations_section})
            final_report = _section_synthesiser(state)
            logger.info(f"TNA completed and report saved successfully.\n{final_report[:100]}...")
            return final_report
    except Exception as e:
        logger.critical(f"An error occurred while running the TNA automation workflow:{str(e)}")
    return None