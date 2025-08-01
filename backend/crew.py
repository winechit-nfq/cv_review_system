from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class CrewAI():

    agents: List[BaseAgent]
    tasks: List[Task]

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def technical_architect_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['technical_architect_agent'], 
            verbose=True
        )

    @agent
    def engineering_practice_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['engineering_practice_agent'], 
            verbose=True
        )
    
    @agent
    def team_leadership_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['team_leadership_agent'], 
            verbose=True
        )

    @agent
    def software_engineer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['software_engineer_agent'], 
            verbose=True
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def technical_architecture_review_task(self) -> Task:
        return Task(
            config=self.tasks_config['technical_architecture_review_task'], 
        )

    @task
    def engineering_practice_review_task(self) -> Task:
        return Task(
            config=self.tasks_config['engineering_practice_review_task'], 
        )

    @task
    def team_leadership_review_task(self) -> Task:
        return Task(
            config=self.tasks_config['team_leadership_review_task'],
        )

    @task
    def software_engineer_cv_review_task(self) -> Task:
        return Task(
            config=self.tasks_config['software_engineer_cv_review_task'],
            async_execution=True,
            output_file='report.md'
        )

    @crew
    def crew(self) -> Crew:
        """Creates the LatestAiDevelopment crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
