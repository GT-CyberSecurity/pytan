GETF = "Use GetObject to find {} objects with cache filters to limit the results"
GET = "Use GetObject to find all {} objects"
SQ_GETQ = "Use GetObject to get the last question asked by a saved question"
SQ_RI = (
    "Use GetResultInfo on a saved question in order to issue a new question, "
    "which refreshes the data for that saved question"
)
SQ_RESQ = (
    "Use GetObject to re-fetch the saved question in order get the ID of the newly asked question"
)
PJ = "Use AddObject to add a ParseJob for question_text and get back ParseResultGroups"
PJ_ADD = "Use AddObject to add the Question object from the chosen ParseResultGroup"
GRD = "Use GetResultData to get answers for {} object"
GRD_SSE = "Issue a GetResultData on {} to start a Server Side Export and get an export_id"
GRI = "Issue a GetResultInfo for a {} to check the current progress of answers"
ADD = "Issue an AddObject to add a {} object"
ADDGET = "Issue a GetObject on the recently added {} object in order to get the full object"
SAA = "Issue an AddObject to add a SavedActionApproval"
STOPA = "Issue an AddObject to add a StopAction"
STOPAR = "Re-issue a GetObject to ensure the actions stopped_flag is 1"
AUTH = "Authenticate to the SOAP API via /auth"
SERVINFO = "Get the server version via /info.json"
GRI_RETRY = "Re-issuing a GetResultInfo since the estimated_total came back 0, {}"
SSE_PROGRESS = "Perform an HTTP get to retrieve the status of a server side export"
SSE_GET = "Perform an HTTP get to retrieve the data of a server side export"
DEL = "Issue a DeleteObject to delete an object"
