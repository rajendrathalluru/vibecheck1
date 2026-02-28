from api.agents.auth_agent import AuthAgent
from api.agents.config_agent import ConfigAgent
from api.agents.injection_agent import InjectionAgent
from api.agents.recon_agent import ReconAgent

AGENT_MAP = {
    "recon": ReconAgent,
    "auth": AuthAgent,
    "injection": InjectionAgent,
    "config": ConfigAgent,
}
