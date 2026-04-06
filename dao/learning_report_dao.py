# 文件路径: dao/learning_report_dao.py
from models.learning_report import LearningReport
from utils.db import Session

class LearningReportDAO:
    @staticmethod
    def get_reports(user_id, report_type=None, symbol=None, limit=200):
        session = Session()
        try:
            query = session.query(LearningReport).filter_by(user_id=user_id)
            if report_type:
                query = query.filter_by(report_type=report_type)
            if symbol:
                query = query.filter_by(symbol=symbol)
            return query.order_by(LearningReport.created_at.desc()).limit(limit).all()
        finally:
            session.close()