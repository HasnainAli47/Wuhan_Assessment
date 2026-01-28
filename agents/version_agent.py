"""
Version Control Agent - Handles Document History and Contributions

================================================================================
DEVELOPED BY: Hasnain Ali | Wuhan University | Supervisor: Prof. Liang Peng
================================================================================

EXPLANATION FOR VIVA:
=====================
This agent manages version control for documents, similar to Git but for documents.

Key Responsibilities:
1. Maintain Version History - Store document snapshots
2. Revert to Previous Versions - Restore old content
3. Track User Contributions - Who wrote what

Version Control Concepts:
- Snapshot: Complete copy of document at a point in time
- Diff: The differences between two versions
- Revert: Restore to a previous state
- Contribution: Track individual user's input

Why Version Control?
1. Undo mistakes: Go back to working versions
2. Track history: See how document evolved
3. Attribution: Know who contributed what
4. Collaboration: Multiple people can work without fear of losing data

This is similar to:
- Git for code
- Google Docs version history
- Wikipedia revision history
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
import difflib

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent_base import Agent, AgentMessage, MessageType
from core.event_bus import EventBus, Event, EventType
from models.database import get_session
from models.document import Document
from models.user import User
from models.version import Version, DocumentChange, get_contribution_stats

logger = logging.getLogger(__name__)


class VersionControlAgent(Agent):
    """
    Agent responsible for version control operations.
    
    EXPLANATION FOR VIVA:
    ====================
    This agent implements Git-like functionality for documents:
    
    Operations Implemented (as required):
    1. Maintain Version History (create_version, get_history)
    2. Revert to Previous Versions (revert_version)
    3. Track User Contributions (get_contributions)
    
    Plus additional operations:
    4. Compare Versions (diff)
    5. Get Specific Version
    
    Design Decisions:
    - Full snapshots vs diffs: We store full content for simplicity
    - Auto-versioning: Could auto-save versions periodically
    - Version numbers: Sequential integers (1, 2, 3...)
    
    Similar to Git but simpler:
    - No branching (linear history)
    - No merging (would need conflict resolution)
    - Full snapshots (not delta compression)
    """
    
    def __init__(self):
        super().__init__(
            agent_id="version_control_agent",
            name="Version Control Agent"
        )
        self.event_bus = EventBus()
        
        # Configuration
        self.auto_version_interval = 300  # Auto-save version every 5 minutes
        self.max_versions_per_document = 100  # Limit versions to prevent bloat
        
        # Register message handlers
        self.register_handler(MessageType.VERSION_CREATE, self._handle_create_version)
        self.register_handler(MessageType.VERSION_GET_HISTORY, self._handle_get_history)
        self.register_handler(MessageType.VERSION_REVERT, self._handle_revert)
        self.register_handler(MessageType.VERSION_COMPARE, self._handle_compare)
        self.register_handler(MessageType.VERSION_GET_CONTRIBUTIONS, self._handle_get_contributions)
    
    def get_capabilities(self) -> List[MessageType]:
        """Return message types this agent handles."""
        return [
            MessageType.VERSION_CREATE,
            MessageType.VERSION_GET_HISTORY,
            MessageType.VERSION_REVERT,
            MessageType.VERSION_COMPARE,
            MessageType.VERSION_GET_CONTRIBUTIONS
        ]
    
    async def on_start(self):
        """Initialize the agent."""
        logger.info(f"{self.name} started and ready")
    
    async def on_stop(self):
        """Cleanup on shutdown."""
        logger.info(f"{self.name} stopping")
    
    # ==================== VERSION OPERATIONS ====================
    
    async def _handle_create_version(self, message: AgentMessage) -> AgentMessage:
        """
        Create a new version of a document.
        
        EXPLANATION FOR VIVA:
        ====================
        Version creation process:
        1. Get document's current content
        2. Determine next version number
        3. Create version snapshot
        4. Store in database
        5. Publish event
        
        When to create versions:
        - Manual save (user clicks save)
        - Auto-save (periodic)
        - Before major edits
        - When closing document
        
        Version includes:
        - Full content snapshot
        - Who created it
        - When
        - Optional summary
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")
        title = payload.get("title")
        content = payload.get("content")
        change_summary = payload.get("change_summary", "")
        
        if not document_id or not user_id:
            return message.create_response(
                {"success": False, "error": "document_id and user_id required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Get document if content not provided
                if content is None or title is None:
                    doc_result = await session.execute(
                        select(Document).where(Document.id == document_id)
                    )
                    document = doc_result.scalar_one_or_none()
                    
                    if not document:
                        return message.create_response(
                            {"success": False, "error": "Document not found"},
                            success=False
                        )
                    
                    content = content if content is not None else document.content
                    title = title if title is not None else document.title
                
                # Get the latest version to check for changes
                latest_version_result = await session.execute(
                    select(Version).where(
                        Version.document_id == document_id
                    ).order_by(Version.version_number.desc()).limit(1)
                )
                latest_version = latest_version_result.scalar_one_or_none()
                
                # Check if content is the same as the latest version
                if latest_version and latest_version.content == content:
                    return message.create_response({
                        "success": False,
                        "error": "No changes detected. Content is identical to the latest version.",
                        "no_changes": True
                    }, success=False)
                
                # Get next version number
                max_version = latest_version.version_number if latest_version else 0
                next_version = max_version + 1
                
                # Check version limit
                if next_version > self.max_versions_per_document:
                    # Could implement version pruning here
                    logger.warning(f"Document {document_id} has many versions ({next_version})")
                
                # Create version
                version = Version(
                    document_id=document_id,
                    version_number=next_version,
                    title=title,
                    content=content,
                    created_by=user_id,
                    change_summary=change_summary,
                    word_count=len(content.split()) if content else 0,
                    character_count=len(content) if content else 0
                )
                
                session.add(version)
                await session.commit()
                await session.refresh(version)
                
                logger.info(f"Version {next_version} created for document {document_id}")
                
                # Publish event
                await self.event_bus.publish(Event(
                    event_type=EventType.VERSION_CREATED,
                    data={
                        "document_id": document_id,
                        "version": version.to_dict(),
                        "created_by": user_id
                    },
                    user_id=user_id,
                    document_id=document_id
                ))
                
                return message.create_response({
                    "success": True,
                    "version": version.to_dict(),
                    "message": f"Version {next_version} created"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Create version error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_get_history(self, message: AgentMessage) -> AgentMessage:
        """
        Get version history for a document.
        
        EXPLANATION FOR VIVA:
        ====================
        Returns list of all versions with metadata:
        - Version number
        - Who created it
        - When
        - Change summary
        - Word/character counts
        
        Content is not included by default (too large for lists).
        User can request specific version to see content.
        
        This enables the "Version History" panel in the UI.
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")
        limit = payload.get("limit", 50)
        include_content = payload.get("include_content", False)
        
        if not document_id:
            return message.create_response(
                {"success": False, "error": "document_id required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Get document to check permissions
                doc_result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = doc_result.scalar_one_or_none()
                
                if not document:
                    return message.create_response(
                        {"success": False, "error": "Document not found"},
                        success=False
                    )
                
                # Check view permission
                if user_id and not document.can_view(user_id):
                    return message.create_response(
                        {"success": False, "error": "Access denied"},
                        success=False
                    )
                
                # Get versions
                result = await session.execute(
                    select(Version).where(
                        Version.document_id == document_id
                    ).order_by(Version.version_number.desc()).limit(limit)
                )
                versions = result.scalars().all()
                
                return message.create_response({
                    "success": True,
                    "versions": [v.to_dict(include_content=include_content) for v in versions],
                    "total_versions": len(versions),
                    "document_id": document_id
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Get history error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_revert(self, message: AgentMessage) -> AgentMessage:
        """
        Revert document to a previous version.
        
        EXPLANATION FOR VIVA:
        ====================
        Revert process:
        1. Find the target version
        2. Verify user has edit permission
        3. Copy version content to document
        4. Create new version to track the revert
        5. Publish event
        
        Important: Revert creates a NEW version, not delete history.
        Version history: v1 -> v2 -> v3 -> revert to v1 -> v4 (copy of v1)
        
        This preserves the complete history and allows reverting the revert.
        
        This is like Git's "git revert" (not "git reset --hard")
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        version_id = payload.get("version_id")  # Can use ID
        version_number = payload.get("version_number")  # Or version number
        user_id = payload.get("user_id")
        
        if not document_id or not user_id:
            return message.create_response(
                {"success": False, "error": "document_id and user_id required"},
                success=False
            )
        
        if not version_id and not version_number:
            return message.create_response(
                {"success": False, "error": "version_id or version_number required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Get document
                doc_result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = doc_result.scalar_one_or_none()
                
                if not document:
                    return message.create_response(
                        {"success": False, "error": "Document not found"},
                        success=False
                    )
                
                # Check edit permission
                if not document.can_edit(user_id):
                    return message.create_response(
                        {"success": False, "error": "Edit permission denied"},
                        success=False
                    )
                
                # Get target version
                if version_id:
                    ver_result = await session.execute(
                        select(Version).where(
                            and_(
                                Version.id == version_id,
                                Version.document_id == document_id
                            )
                        )
                    )
                else:
                    ver_result = await session.execute(
                        select(Version).where(
                            and_(
                                Version.version_number == version_number,
                                Version.document_id == document_id
                            )
                        )
                    )
                
                target_version = ver_result.scalar_one_or_none()
                
                if not target_version:
                    return message.create_response(
                        {"success": False, "error": "Version not found"},
                        success=False
                    )
                
                # Store current content for the new version
                old_content = document.content
                old_title = document.title
                
                # Revert document content
                document.content = target_version.content
                document.title = target_version.title
                document.update_counts()
                document.last_edited_by = user_id
                document.updated_at = datetime.utcnow()
                
                await session.commit()
                
                # Create a new version to track the revert
                # Get next version number
                max_ver_result = await session.execute(
                    select(func.max(Version.version_number)).where(
                        Version.document_id == document_id
                    )
                )
                next_version = (max_ver_result.scalar() or 0) + 1
                
                revert_version = Version(
                    document_id=document_id,
                    version_number=next_version,
                    title=document.title,
                    content=document.content,
                    created_by=user_id,
                    change_summary=f"Reverted to version {target_version.version_number}",
                    word_count=document.word_count,
                    character_count=document.character_count
                )
                
                session.add(revert_version)
                await session.commit()
                await session.refresh(document)
                await session.refresh(revert_version)
                
                logger.info(f"Document {document_id} reverted to version {target_version.version_number}")
                
                # Publish event
                await self.event_bus.publish(Event(
                    event_type=EventType.VERSION_REVERTED,
                    data={
                        "document_id": document_id,
                        "reverted_to_version": target_version.version_number,
                        "new_version": revert_version.to_dict(),
                        "reverted_by": user_id
                    },
                    user_id=user_id,
                    document_id=document_id
                ))
                
                return message.create_response({
                    "success": True,
                    "document": document.to_dict(),
                    "reverted_to": target_version.to_dict(),
                    "new_version": revert_version.to_dict(),
                    "message": f"Reverted to version {target_version.version_number}"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Revert error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_compare(self, message: AgentMessage) -> AgentMessage:
        """
        Compare two versions of a document (diff).
        
        EXPLANATION FOR VIVA:
        ====================
        Diff (difference) shows what changed between versions:
        - Added lines (in green typically)
        - Removed lines (in red typically)
        - Changed lines (show both old and new)
        
        We use Python's difflib for comparison.
        Output formats:
        - unified: Standard diff format (like git diff)
        - html: For display in UI
        - stats: Just counts
        
        This enables features like:
        - "What changed in this version?"
        - "Compare my version with current"
        - Code review-style viewing
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        version1 = payload.get("version1")  # Version number or "current"
        version2 = payload.get("version2")  # Version number
        output_format = payload.get("format", "unified")  # unified, html, stats
        
        if not document_id:
            return message.create_response(
                {"success": False, "error": "document_id required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Get document for current content
                doc_result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = doc_result.scalar_one_or_none()
                
                if not document:
                    return message.create_response(
                        {"success": False, "error": "Document not found"},
                        success=False
                    )
                
                # Get content for version 1
                if version1 == "current":
                    content1 = document.content
                    title1 = f"Current ({document.title})"
                else:
                    ver1_result = await session.execute(
                        select(Version).where(
                            and_(
                                Version.document_id == document_id,
                                Version.version_number == version1
                            )
                        )
                    )
                    ver1 = ver1_result.scalar_one_or_none()
                    if not ver1:
                        return message.create_response(
                            {"success": False, "error": f"Version {version1} not found"},
                            success=False
                        )
                    content1 = ver1.content
                    title1 = f"Version {version1}"
                
                # Get content for version 2
                if version2 == "current":
                    content2 = document.content
                    title2 = f"Current ({document.title})"
                else:
                    ver2_result = await session.execute(
                        select(Version).where(
                            and_(
                                Version.document_id == document_id,
                                Version.version_number == version2
                            )
                        )
                    )
                    ver2 = ver2_result.scalar_one_or_none()
                    if not ver2:
                        return message.create_response(
                            {"success": False, "error": f"Version {version2} not found"},
                            success=False
                        )
                    content2 = ver2.content
                    title2 = f"Version {version2}"
                
                # Generate diff
                diff_result = self._generate_diff(
                    content1, content2, 
                    title1, title2, 
                    output_format
                )
                
                return message.create_response({
                    "success": True,
                    "diff": diff_result,
                    "version1": version1,
                    "version2": version2,
                    "format": output_format
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Compare error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_get_contributions(self, message: AgentMessage) -> AgentMessage:
        """
        Get user contributions for a document.
        
        EXPLANATION FOR VIVA:
        ====================
        Contribution tracking shows:
        - How many changes each user made
        - Characters added/removed by each user
        - Percentage of contributions
        - Version creation counts
        
        This is useful for:
        - Academic attribution (who wrote what percentage)
        - Team metrics (workload distribution)
        - Recognition (highlighting top contributors)
        
        We aggregate data from DocumentChange records AND Version records.
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")  # Optional: filter for specific user
        
        if not document_id:
            return message.create_response(
                {"success": False, "error": "document_id required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Get document to include owner
                doc_result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = doc_result.scalar_one_or_none()
                
                # Get all changes for this document
                result = await session.execute(
                    select(DocumentChange).where(
                        DocumentChange.document_id == document_id
                    )
                )
                changes = result.scalars().all()
                
                # Get all versions for this document (to track version creators)
                version_result = await session.execute(
                    select(Version).where(
                        Version.document_id == document_id
                    )
                )
                versions = version_result.scalars().all()
                
                # Build contributor set from changes, versions, and document owner
                contributors = set()
                
                # Add from changes
                for c in changes:
                    contributors.add(c.user_id)
                
                # Add from version creators
                for v in versions:
                    if v.created_by:
                        contributors.add(v.created_by)
                
                # Add document owner
                if document and document.owner_id:
                    contributors.add(document.owner_id)
                
                # Add last editor
                if document and document.last_edited_by:
                    contributors.add(document.last_edited_by)
                
                if not contributors:
                    return message.create_response({
                        "success": True,
                        "contributions": [],
                        "total_changes": 0,
                        "message": "No contributions recorded yet"
                    })
                
                # Calculate stats for each contributor
                contributions = []
                for contributor_id in contributors:
                    # Get change stats
                    if changes:
                        stats = get_contribution_stats(changes, contributor_id)
                    else:
                        stats = {
                            "user_id": contributor_id,
                            "total_changes": 0,
                            "characters_added": 0,
                            "characters_removed": 0,
                            "percentage": 0
                        }
                    
                    # Count versions created by this user
                    versions_created = len([v for v in versions if v.created_by == contributor_id])
                    stats["versions_created"] = versions_created
                    
                    # Check if owner
                    stats["is_owner"] = document and document.owner_id == contributor_id
                    
                    # Get user info
                    user_result = await session.execute(
                        select(User).where(User.id == contributor_id)
                    )
                    user = user_result.scalar_one_or_none()
                    
                    if user:
                        stats["username"] = user.username
                        stats["display_name"] = user.display_name or user.username
                    else:
                        stats["username"] = "Unknown"
                        stats["display_name"] = "Unknown User"
                    
                    contributions.append(stats)
                
                # Recalculate percentages including version creation
                total_activity = sum(c["total_changes"] + c["versions_created"] for c in contributions)
                if total_activity > 0:
                    for c in contributions:
                        activity = c["total_changes"] + c["versions_created"]
                        c["percentage"] = round((activity / total_activity) * 100, 1)
                elif contributions:
                    # Equal split if no tracked activity
                    equal_share = round(100 / len(contributions), 1)
                    for c in contributions:
                        c["percentage"] = equal_share
                
                # Sort by contribution percentage, owners first
                contributions.sort(key=lambda x: (not x.get("is_owner", False), -x["percentage"]))
                
                # Filter for specific user if requested
                if user_id:
                    contributions = [c for c in contributions if c["user_id"] == user_id]
                
                return message.create_response({
                    "success": True,
                    "contributions": contributions,
                    "total_changes": len(changes),
                    "total_versions": len(versions),
                    "total_contributors": len(contributors)
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Get contributions error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    # ==================== UTILITY METHODS ====================
    
    def _generate_diff(
        self, 
        content1: str, 
        content2: str, 
        title1: str, 
        title2: str,
        output_format: str
    ) -> Dict[str, Any]:
        """
        Generate diff between two content strings.
        
        EXPLANATION FOR VIVA:
        ====================
        Uses Python's difflib to compare texts.
        
        Diff algorithms:
        - unified_diff: Shows changes in context (like git diff)
        - HtmlDiff: Creates HTML table with side-by-side comparison
        
        We also calculate statistics:
        - Lines added/removed
        - Similarity ratio
        """
        lines1 = content1.splitlines(keepends=True)
        lines2 = content2.splitlines(keepends=True)
        
        # Calculate statistics
        matcher = difflib.SequenceMatcher(None, content1, content2)
        similarity = matcher.ratio()
        
        # Count added/removed lines
        added = 0
        removed = 0
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == 'insert':
                added += j2 - j1
            elif opcode == 'delete':
                removed += i2 - i1
            elif opcode == 'replace':
                added += j2 - j1
                removed += i2 - i1
        
        result = {
            "statistics": {
                "similarity": round(similarity * 100, 2),
                "characters_added": added,
                "characters_removed": removed,
                "lines_in_version1": len(lines1),
                "lines_in_version2": len(lines2)
            }
        }
        
        if output_format == "unified":
            # Standard unified diff format
            diff_lines = list(difflib.unified_diff(
                lines1, lines2,
                fromfile=title1, tofile=title2,
                lineterm=""
            ))
            result["diff_text"] = "\n".join(diff_lines)
            
        elif output_format == "html":
            # HTML diff for UI display
            differ = difflib.HtmlDiff()
            result["diff_html"] = differ.make_table(
                lines1, lines2,
                fromdesc=title1, todesc=title2,
                context=True
            )
            
        elif output_format == "stats":
            # Only statistics, no actual diff
            pass
        
        return result
    
    async def get_version(self, document_id: str, version_number: int) -> Optional[Version]:
        """Get a specific version by number."""
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(Version).where(
                        and_(
                            Version.document_id == document_id,
                            Version.version_number == version_number
                        )
                    )
                )
                return result.scalar_one_or_none()
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Get version error: {e}")
            return None
    
    async def get_latest_version(self, document_id: str) -> Optional[Version]:
        """Get the latest version of a document."""
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(Version).where(
                        Version.document_id == document_id
                    ).order_by(Version.version_number.desc()).limit(1)
                )
                return result.scalar_one_or_none()
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Get latest version error: {e}")
            return None
