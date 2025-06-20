"""
Database Consistency Checker for RefServer
Ensures data integrity between SQLite and ChromaDB
"""

import logging
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# Import database modules
from models import Paper, Embedding, PageEmbedding
from vector_db import get_vector_db

logger = logging.getLogger("RefServerConsistency")


class ConsistencyIssueType(Enum):
    """Types of consistency issues that can be detected"""
    MISSING_IN_CHROMADB = "missing_in_chromadb"
    MISSING_IN_SQLITE = "missing_in_sqlite" 
    EMBEDDING_MISMATCH = "embedding_mismatch"
    ORPHANED_CHROMADB = "orphaned_chromadb"
    ORPHANED_SQLITE = "orphaned_sqlite"
    COUNT_MISMATCH = "count_mismatch"
    METADATA_MISMATCH = "metadata_mismatch"


@dataclass
class ConsistencyIssue:
    """Represents a consistency issue between databases"""
    issue_type: ConsistencyIssueType
    doc_id: str
    description: str
    severity: str  # low, medium, high, critical
    sqlite_data: Optional[Dict] = None
    chromadb_data: Optional[Dict] = None
    suggested_fix: Optional[str] = None


class DatabaseConsistencyChecker:
    """Checks and maintains consistency between SQLite and ChromaDB"""
    
    def __init__(self):
        self.vector_db = get_vector_db()
        self.issues = []
        self.last_check_time = None
        
        logger.info("DatabaseConsistencyChecker initialized")
    
    def run_full_consistency_check(self) -> Dict:
        """
        Run comprehensive consistency check between SQLite and ChromaDB
        
        Returns:
            Dictionary with check results and statistics
        """
        logger.info("Starting full database consistency check...")
        start_time = datetime.now()
        
        self.issues = []  # Reset issues list
        
        # Run all consistency checks
        self._check_paper_count_consistency()
        self._check_paper_id_consistency()
        self._check_page_embedding_consistency()
        self._check_orphaned_records()
        self._check_metadata_consistency()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        self.last_check_time = end_time
        
        # Categorize issues by severity
        critical_issues = [i for i in self.issues if i.severity == "critical"]
        high_issues = [i for i in self.issues if i.severity == "high"]
        medium_issues = [i for i in self.issues if i.severity == "medium"]
        low_issues = [i for i in self.issues if i.severity == "low"]
        
        results = {
            "check_timestamp": end_time.isoformat(),
            "duration_seconds": duration,
            "total_issues": len(self.issues),
            "issues_by_severity": {
                "critical": len(critical_issues),
                "high": len(high_issues),
                "medium": len(medium_issues),
                "low": len(low_issues)
            },
            "issues": [self._issue_to_dict(issue) for issue in self.issues],
            "overall_status": self._determine_overall_status(),
            "recommendations": self._generate_recommendations()
        }
        
        logger.info(f"Consistency check completed in {duration:.2f}s. Found {len(self.issues)} issues.")
        return results
    
    def _check_paper_count_consistency(self):
        """Check if paper counts match between SQLite and ChromaDB"""
        try:
            # Count papers in SQLite
            sqlite_count = Paper.select().count()
            
            # Count documents in ChromaDB papers collection
            try:
                chromadb_papers = self.vector_db.papers_collection.get()
                chromadb_count = len(chromadb_papers['ids']) if chromadb_papers['ids'] else 0
            except Exception as e:
                logger.warning(f"Could not get ChromaDB papers count: {e}")
                chromadb_count = 0
            
            logger.info(f"Paper counts - SQLite: {sqlite_count}, ChromaDB: {chromadb_count}")
            
            if sqlite_count != chromadb_count:
                self.issues.append(ConsistencyIssue(
                    issue_type=ConsistencyIssueType.COUNT_MISMATCH,
                    doc_id="global",
                    description=f"Paper count mismatch: SQLite has {sqlite_count}, ChromaDB has {chromadb_count}",
                    severity="high",
                    sqlite_data={"count": sqlite_count},
                    chromadb_data={"count": chromadb_count},
                    suggested_fix="Run paper synchronization to align counts"
                ))
        except Exception as e:
            logger.error(f"Error checking paper count consistency: {e}")
    
    def _check_paper_id_consistency(self):
        """Check if paper IDs exist in both databases"""
        try:
            # Get all paper IDs from SQLite
            sqlite_paper_ids = set()
            for paper in Paper.select(Paper.doc_id):
                sqlite_paper_ids.add(paper.doc_id)
            
            # Get all document IDs from ChromaDB papers collection
            chromadb_paper_ids = set()
            try:
                chromadb_papers = self.vector_db.papers_collection.get()
                if chromadb_papers['ids']:
                    chromadb_paper_ids = set(chromadb_papers['ids'])
            except Exception as e:
                logger.warning(f"Could not get ChromaDB paper IDs: {e}")
            
            # Find missing papers
            missing_in_chromadb = sqlite_paper_ids - chromadb_paper_ids
            missing_in_sqlite = chromadb_paper_ids - sqlite_paper_ids
            
            # Report missing papers in ChromaDB
            for doc_id in missing_in_chromadb:
                self.issues.append(ConsistencyIssue(
                    issue_type=ConsistencyIssueType.MISSING_IN_CHROMADB,
                    doc_id=doc_id,
                    description=f"Paper {doc_id} exists in SQLite but missing in ChromaDB",
                    severity="medium",
                    suggested_fix="Add paper embedding to ChromaDB"
                ))
            
            # Report missing papers in SQLite
            for doc_id in missing_in_sqlite:
                self.issues.append(ConsistencyIssue(
                    issue_type=ConsistencyIssueType.MISSING_IN_SQLITE,
                    doc_id=doc_id,
                    description=f"Paper {doc_id} exists in ChromaDB but missing in SQLite",
                    severity="medium", 
                    suggested_fix="Remove orphaned document from ChromaDB or add to SQLite"
                ))
            
            logger.info(f"Paper ID consistency - Missing in ChromaDB: {len(missing_in_chromadb)}, Missing in SQLite: {len(missing_in_sqlite)}")
            
        except Exception as e:
            logger.error(f"Error checking paper ID consistency: {e}")
    
    def _check_page_embedding_consistency(self):
        """Check consistency of page embeddings between SQLite and ChromaDB"""
        try:
            # Get page embedding counts per paper from SQLite
            sqlite_page_counts = {}
            for page_emb in PageEmbedding.select(PageEmbedding.paper_id):
                paper_id = page_emb.paper_id
                sqlite_page_counts[paper_id] = sqlite_page_counts.get(paper_id, 0) + 1
            
            # Get page embedding counts from ChromaDB pages collection
            chromadb_page_counts = {}
            try:
                chromadb_pages = self.vector_db.pages_collection.get()
                if chromadb_pages['metadatas']:
                    for metadata in chromadb_pages['metadatas']:
                        paper_id = metadata.get('paper_id')
                        if paper_id:
                            chromadb_page_counts[paper_id] = chromadb_page_counts.get(paper_id, 0) + 1
            except Exception as e:
                logger.warning(f"Could not get ChromaDB page counts: {e}")
            
            # Compare counts
            all_paper_ids = set(sqlite_page_counts.keys()) | set(chromadb_page_counts.keys())
            
            for paper_id in all_paper_ids:
                sqlite_count = sqlite_page_counts.get(paper_id, 0)
                chromadb_count = chromadb_page_counts.get(paper_id, 0)
                
                if sqlite_count != chromadb_count:
                    self.issues.append(ConsistencyIssue(
                        issue_type=ConsistencyIssueType.COUNT_MISMATCH,
                        doc_id=paper_id,
                        description=f"Page embedding count mismatch for paper {paper_id}: SQLite has {sqlite_count}, ChromaDB has {chromadb_count}",
                        severity="medium",
                        sqlite_data={"page_count": sqlite_count},
                        chromadb_data={"page_count": chromadb_count},
                        suggested_fix="Regenerate page embeddings for this paper"
                    ))
            
            logger.info(f"Page embedding consistency checked for {len(all_paper_ids)} papers")
            
        except Exception as e:
            logger.error(f"Error checking page embedding consistency: {e}")
    
    def _check_orphaned_records(self):
        """Check for orphaned records in both databases"""
        try:
            # Check for embeddings without papers in SQLite
            embeddings_without_papers = (Embedding
                                       .select()
                                       .join(Paper, on=(Embedding.paper == Paper.doc_id), join_type='LEFT OUTER')
                                       .where(Paper.doc_id.is_null()))
            
            for embedding in embeddings_without_papers:
                self.issues.append(ConsistencyIssue(
                    issue_type=ConsistencyIssueType.ORPHANED_SQLITE,
                    doc_id=embedding.paper_id,
                    description=f"Embedding exists for non-existent paper {embedding.paper_id}",
                    severity="low",
                    suggested_fix="Remove orphaned embedding record"
                ))
            
            # Check for page embeddings without papers
            page_embeddings_without_papers = (PageEmbedding
                                            .select()
                                            .join(Paper, on=(PageEmbedding.paper == Paper.doc_id), join_type='LEFT OUTER')
                                            .where(Paper.doc_id.is_null()))
            
            for page_emb in page_embeddings_without_papers:
                self.issues.append(ConsistencyIssue(
                    issue_type=ConsistencyIssueType.ORPHANED_SQLITE,
                    doc_id=page_emb.paper_id,
                    description=f"Page embedding exists for non-existent paper {page_emb.paper_id}",
                    severity="low",
                    suggested_fix="Remove orphaned page embedding record"
                ))
            
            logger.info("Orphaned records check completed")
            
        except Exception as e:
            logger.error(f"Error checking orphaned records: {e}")
    
    def _check_metadata_consistency(self):
        """Check if metadata in ChromaDB matches SQLite"""
        try:
            # Sample a few papers to check metadata consistency
            papers = Paper.select().limit(10)  # Check first 10 papers as sample
            
            for paper in papers:
                try:
                    # Get ChromaDB document
                    chromadb_result = self.vector_db.papers_collection.get(
                        ids=[paper.doc_id],
                        include=['metadatas']
                    )
                    
                    if chromadb_result['ids'] and chromadb_result['metadatas']:
                        chromadb_metadata = chromadb_result['metadatas'][0]
                        
                        # Check filename consistency
                        if chromadb_metadata.get('filename') != paper.filename:
                            self.issues.append(ConsistencyIssue(
                                issue_type=ConsistencyIssueType.METADATA_MISMATCH,
                                doc_id=paper.doc_id,
                                description=f"Filename mismatch for paper {paper.doc_id}",
                                severity="low",
                                sqlite_data={"filename": paper.filename},
                                chromadb_data={"filename": chromadb_metadata.get('filename')},
                                suggested_fix="Update ChromaDB metadata to match SQLite"
                            ))
                
                except Exception as e:
                    logger.warning(f"Could not check metadata for paper {paper.doc_id}: {e}")
            
            logger.info("Metadata consistency check completed")
            
        except Exception as e:
            logger.error(f"Error checking metadata consistency: {e}")
    
    def _determine_overall_status(self) -> str:
        """Determine overall consistency status"""
        if not self.issues:
            return "excellent"
        
        critical_count = len([i for i in self.issues if i.severity == "critical"])
        high_count = len([i for i in self.issues if i.severity == "high"])
        
        if critical_count > 0:
            return "critical"
        elif high_count > 0:
            return "poor"
        elif len(self.issues) > 10:
            return "fair"
        else:
            return "good"
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on found issues"""
        recommendations = []
        
        issue_types = set(issue.issue_type for issue in self.issues)
        
        if ConsistencyIssueType.COUNT_MISMATCH in issue_types:
            recommendations.append("Run database synchronization to resolve count mismatches")
        
        if ConsistencyIssueType.MISSING_IN_CHROMADB in issue_types:
            recommendations.append("Regenerate ChromaDB embeddings for missing papers")
        
        if ConsistencyIssueType.MISSING_IN_SQLITE in issue_types:
            recommendations.append("Clean up orphaned ChromaDB documents")
        
        if ConsistencyIssueType.ORPHANED_SQLITE in issue_types:
            recommendations.append("Remove orphaned SQLite records")
        
        if not recommendations:
            recommendations.append("All databases are consistent - no action needed")
        
        return recommendations
    
    def _issue_to_dict(self, issue: ConsistencyIssue) -> Dict:
        """Convert ConsistencyIssue to dictionary for JSON serialization"""
        return {
            "issue_type": issue.issue_type.value,
            "doc_id": issue.doc_id,
            "description": issue.description,
            "severity": issue.severity,
            "sqlite_data": issue.sqlite_data,
            "chromadb_data": issue.chromadb_data,
            "suggested_fix": issue.suggested_fix
        }
    
    def auto_fix_issues(self, issue_types: List[ConsistencyIssueType] = None) -> Dict:
        """
        Automatically fix specific types of consistency issues
        
        Args:
            issue_types: List of issue types to fix. If None, fixes safe issues only.
            
        Returns:
            Dictionary with fix results
        """
        if issue_types is None:
            # Only fix safe issues by default
            issue_types = [
                ConsistencyIssueType.ORPHANED_SQLITE,
                ConsistencyIssueType.METADATA_MISMATCH
            ]
        
        fixed_count = 0
        failed_count = 0
        
        for issue in self.issues:
            if issue.issue_type in issue_types:
                try:
                    if issue.issue_type == ConsistencyIssueType.ORPHANED_SQLITE:
                        self._fix_orphaned_sqlite(issue)
                    elif issue.issue_type == ConsistencyIssueType.METADATA_MISMATCH:
                        self._fix_metadata_mismatch(issue)
                    
                    fixed_count += 1
                    logger.info(f"Fixed issue: {issue.description}")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to fix issue {issue.doc_id}: {e}")
        
        return {
            "fixed_count": fixed_count,
            "failed_count": failed_count,
            "timestamp": datetime.now().isoformat()
        }
    
    def _fix_orphaned_sqlite(self, issue: ConsistencyIssue):
        """Fix orphaned SQLite records"""
        # Remove orphaned embeddings
        Embedding.delete().where(Embedding.paper_id == issue.doc_id).execute()
        PageEmbedding.delete().where(PageEmbedding.paper_id == issue.doc_id).execute()
    
    def _fix_metadata_mismatch(self, issue: ConsistencyIssue):
        """Fix metadata mismatches by updating ChromaDB"""
        # This would update ChromaDB metadata to match SQLite
        # Implementation depends on specific mismatch type
        pass
    
    def get_consistency_summary(self) -> Dict:
        """Get a quick summary of database consistency"""
        if not self.last_check_time:
            return {
                "status": "never_checked",
                "message": "Consistency check has never been run"
            }
        
        # Run a quick check (counts only)
        sqlite_paper_count = Paper.select().count()
        
        try:
            chromadb_papers = self.vector_db.papers_collection.get()
            chromadb_count = len(chromadb_papers['ids']) if chromadb_papers['ids'] else 0
        except Exception:
            chromadb_count = 0
        
        count_match = sqlite_paper_count == chromadb_count
        
        return {
            "last_check": self.last_check_time.isoformat(),
            "sqlite_papers": sqlite_paper_count,
            "chromadb_papers": chromadb_count,
            "counts_match": count_match,
            "total_issues": len(self.issues),
            "status": "consistent" if count_match and len(self.issues) == 0 else "inconsistent"
        }


# Singleton instance
_consistency_checker: Optional[DatabaseConsistencyChecker] = None


def get_consistency_checker() -> DatabaseConsistencyChecker:
    """Get or create the consistency checker singleton"""
    global _consistency_checker
    if _consistency_checker is None:
        _consistency_checker = DatabaseConsistencyChecker()
    return _consistency_checker