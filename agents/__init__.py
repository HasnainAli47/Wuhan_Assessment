# Agents Module
# Contains the three main agents for the collaborative editing system

from .user_agent import UserManagementAgent
from .document_agent import DocumentEditingAgent
from .version_agent import VersionControlAgent

__all__ = ['UserManagementAgent', 'DocumentEditingAgent', 'VersionControlAgent']
