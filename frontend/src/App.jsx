import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [purchaseOrder, setPurchaseOrder] = useState(null);
  const [jobOrder, setJobOrder] = useState(null);
  const [testReports, setTestReports] = useState(null);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const [selectedLab, setSelectedLab] = useState(null);

  const [activeView, setActiveView] = useState("analyze");

  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  // Separate ISO / NABL report compliance page.
  // These results never change normal technical job statuses.
  const [complianceReport, setComplianceReport] = useState(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [complianceResult, setComplianceResult] = useState(null);
  const [selectedComplianceReport, setSelectedComplianceReport] =
    useState(null);

  const [selectedHistoryJob, setSelectedHistoryJob] =
    useState(null);

  const [selectedHistoryLab, setSelectedHistoryLab] =
    useState(null);

  const [historyLoading, setHistoryLoading] =
    useState(false);

  const [reviewDecisionLoading, setReviewDecisionLoading] =
    useState(false);

  const [reviewNote, setReviewNote] = useState("");

  const [reviewedBy, setReviewedBy] =
    useState("Lab Engineer");
const API_URL = "http://localhost:8001";

  const UploadCard = ({ title, subtitle, file, setFile }) => {
    return (
      <label className={`simple-upload-box ${file ? "selected" : ""}`}>
        <input
          type="file"
          accept=".pdf"
          hidden
          onChange={(e) => setFile(e.target.files[0])}
        />
        <div className="simple-upload-icon">↑</div>
        <strong>{title}</strong>
        <span className="simple-upload-subtitle">{subtitle}</span>
        <span className={file ? "simple-file-name" : "simple-upload-action"}>
          {file ? `✓ ${file.name}` : "Click to upload PDF"}
        </span>
        <small>{file ? "Click to replace" : "PDF files only"}</small>
      </label>
    );
  };


  const analyzeDocuments = async () => {
    if (
      !purchaseOrder ||
      !jobOrder ||
      !testReports
    ) {
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setSelectedLab(null);

    const formData = new FormData();

    formData.append(
      "purchase_order_file",
      purchaseOrder
    );

    formData.append(
      "job_order_file",
      jobOrder
    );

    formData.append(
      "reports_file",
      testReports
    );

    try {
      const response = await fetch(
        `${API_URL}/analyze-job`,
        {
          method: "POST",
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error(
          "Document analysis failed."
        );
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      setResult(data);

              if (data.saved_job?.job_id) {
          try {
            const savedResponse = await fetch(
              `${API_URL}/jobs/${data.saved_job.job_id}`
            );

            if (!savedResponse.ok) {
              throw new Error(
                "Analysis completed, but saved lab details could not be loaded."
              );
            }

            const savedData =
              await savedResponse.json();

            setResult({
              ...data,
              saved_job_details: savedData
            });

          } catch (savedError) {
            setResult(data);

            console.error(
              savedError
            );
          }

        } else {
          setResult(data);
        }

    } catch (err) {
      setError(
        err.message ||
        "Something went wrong."
      );

    } finally {
      setLoading(false);
    }
  };


  const analyzeReportCompliance = async () => {
    if (!complianceReport) {
      return;
    }

    setComplianceLoading(true);
    setError("");
    setComplianceResult(null);
    setSelectedComplianceReport(null);

    const formData = new FormData();

    formData.append(
      "reports_file",
      complianceReport
    );

    try {
      const response = await fetch(
        `${API_URL}/analyze-report-compliance`,
        {
          method: "POST",
          body: formData
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "ISO / NABL report compliance check failed."
        );
      }

      setComplianceResult(data);

    } catch (err) {
      setError(
        err.message ||
        "ISO / NABL report compliance check failed."
      );

    } finally {
      setComplianceLoading(false);
    }
  };


  const loadJobs = async () => {
    setJobsLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/jobs`
      );

      if (!response.ok) {
        throw new Error(
          "Could not load job history."
        );
      }

      const data = await response.json();

      setJobs(data);

    } catch (err) {
      setError(
        err.message ||
        "Could not load job history."
      );

    } finally {
      setJobsLoading(false);
    }
  };


  const loadHistoryJob = async (jobId) => {
    setHistoryLoading(true);
    setSelectedHistoryJob(null);
    setSelectedHistoryLab(null);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/jobs/${jobId}`
      );

      if (!response.ok) {
        throw new Error(
          "Could not load job details."
        );
      }

      const data = await response.json();

      setSelectedHistoryJob(data);

    } catch (err) {
      setError(
        err.message ||
        "Could not load job details."
      );

    } finally {
      setHistoryLoading(false);
    }
  };


  const submitManualReview = async (
  labId,
  decision
) => {
  if (!labId) {
    setError(
      "Lab database ID is missing."
    );
    return;
  }

  setReviewDecisionLoading(true);
  setError("");

  try {
    const response = await fetch(
      `${API_URL}/labs/${labId}/review`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          decision: decision,
          note: reviewNote,
          reviewed_by: reviewedBy
        })
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Manual review failed."
      );
    }

    // Update selected lab immediately
    setSelectedLab((current) => ({
      ...current,
      review_status:
        data.review_status,
      review_note:
        data.review_note,
      reviewed_by:
        data.reviewed_by,
      reviewed_at:
        data.reviewed_at
    }));

    // Update top job status immediately
    setResult((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,

        saved_job: {
          ...current.saved_job,
          overall_status:
            data.job_overall_status
        },

        saved_job_details:
          current.saved_job_details
            ? {
                ...current.saved_job_details,

                overall_status:
                  data.job_overall_status,

                labs:
                  current
                    .saved_job_details
                    .labs
                    .map((lab) =>
                      lab.id === labId
                        ? {
                            ...lab,
                            review_status:
                              data.review_status,
                            review_note:
                              data.review_note,
                            reviewed_by:
                              data.reviewed_by,
                            reviewed_at:
                              data.reviewed_at
                          }
                        : lab
                    )
              }
            : current.saved_job_details
      };
    });

    setReviewNote("");

    // Refresh history list in background
    try {
      const jobsResponse = await fetch(
        `${API_URL}/jobs`
      );

      if (jobsResponse.ok) {
        const jobsData =
          await jobsResponse.json();

        setJobs(jobsData);
      }
    } catch {
      // Review already saved successfully.
    }

  } catch (err) {
    setError(
      err.message ||
      "Manual review failed."
    );

  } finally {
    setReviewDecisionLoading(false);
  }
};


  useEffect(() => {
    if (activeView === "history") {
      loadJobs();
    }
  }, [activeView]);


  const formatTestName = (name) => {
    if (!name) {
      return "-";
    }

    return name
      .replace(
        "_test_report",
        ""
      )
      .replace(
        "_report",
        ""
      )
      .replaceAll(
        "_",
        " "
      )
      .replace(
        /\b\w/g,
        (letter) =>
          letter.toUpperCase()
      );
  };


  const getRecommendedAction = (lab) => {
    if (!lab) {
      return "";
    }

    if (
      lab.review_status ===
      "APPROVED"
    ) {
      return (
        "Manual review completed and approved."
      );
    }

    if (
      lab.review_status ===
      "REJECTED"
    ) {
      return (
        "Manual review rejected this result. Corrective action is required."
      );
    }

    if (
      lab.final_status ===
      "PASS"
    ) {
      return (
        "No action required. All required validations passed."
      );
    }

    if (
      lab.final_status ===
      "MISSING"
    ) {
      return (
        "Upload or complete the missing required test report before approval."
      );
    }

    if (
      lab.final_status ===
      "FAIL"
    ) {
      return (
        "Review the failed test results and take the required corrective action before approval."
      );
    }

    if (
      lab.final_status ===
      "REVIEW"
    ) {
      return (
        "A lab engineer should manually verify the listed issue before final approval."
      );
    }

    return (
      "Manual review is required."
    );
  };


  const getLabDetails = (labNo) => {
    const reportData =
      result
        ?.report_comparison
        ?.[labNo];

    const finalData =
      result
        ?.final_decisions
        ?.[labNo];

    const jobLab =
      result
        ?.job_order
        ?.labs
        ?.find(
          (lab) =>
            lab.lab_no === labNo
        );

    const savedLab =
      result
        ?.saved_job_details
        ?.labs
        ?.find(
          (lab) =>
            lab.lab_no === labNo
        );

    return {
      id:
        savedLab?.id,

      lab_no:
        labNo,

      heat_no:
        jobLab?.heat_no ||
        savedLab?.heat_no ||
        "-",

      required_tests:
        reportData
          ?.required_tests ||
        savedLab
          ?.required_tests ||
        [],

      uploaded_tests:
        reportData
          ?.uploaded_tests ||
        savedLab
          ?.uploaded_tests ||
        [],

      missing_tests:
        reportData
          ?.missing_tests ||
        savedLab
          ?.missing_tests ||
        [],

      test_details:
        reportData
          ?.test_details ||
        savedLab
          ?.report_details ||
        [],

      final_status:
        finalData
          ?.final_status ||
        savedLab
          ?.final_status ||
        "REVIEW",

      reason:
        finalData
          ?.reason ||
        savedLab
          ?.reason ||
        "",

      issues:
        finalData
          ?.issues ||
        savedLab
          ?.issues ||
        [],

      review_status:
        savedLab
          ?.review_status ||
        null,

      review_note:
        savedLab
          ?.review_note ||
        null,

      reviewed_by:
        savedLab
          ?.reviewed_by ||
        null,

      reviewed_at:
        savedLab
          ?.reviewed_at ||
        null
    };
  };


  const formatDate = (value) => {
    if (!value) {
      return "-";
    }

    return new Date(
      value
    ).toLocaleString();
  };


  const resultLines = (detail) => {
    const results = detail?.test_results || {};
    const lines = [];

    if (Array.isArray(results.readings) && results.readings.length) {
      lines.push(`Readings: ${results.readings.join(", ")}`);
    }

    if (results.average !== null && results.average !== undefined) {
      lines.push(`Average: ${results.average}`);
    }

    if (results.temperature_c !== null && results.temperature_c !== undefined) {
      lines.push(`Temperature: ${results.temperature_c} °C`);
    }

    if (results.single_minimum !== null && results.single_minimum !== undefined) {
      lines.push(`Single minimum: ${results.single_minimum} J`);
    }

    if (results.average_minimum !== null && results.average_minimum !== undefined) {
      lines.push(`Average minimum: ${results.average_minimum} J`);
    }

    if (results.elements && Object.keys(results.elements).length) {
      Object.entries(results.elements).forEach(([name, values]) => {
        const limits = [];
        if (values.minimum !== undefined) limits.push(`min ${values.minimum}`);
        if (values.maximum !== undefined) limits.push(`max ${values.maximum}`);
        lines.push(`${name.toUpperCase()}: ${values.result}${limits.length ? ` (${limits.join(", ")})` : ""}`);
      });
    }

    if (Array.isArray(results.parameters) && results.parameters.length) {
      results.parameters.forEach((item) => {
        lines.push(`${item.parameter}: ${item.values?.join(", ") || item.raw || "-"}`);
      });
    }

    if (results.scale) lines.push(`Scale: ${results.scale}`);
    if (results.requirement_text) lines.push(`Requirement: ${results.requirement_text}`);
    if (results.applied_load_kn !== null && results.applied_load_kn !== undefined) {
      lines.push(`Applied load: ${results.applied_load_kn} kN`);
    }
    if (results.required_load_kn !== null && results.required_load_kn !== undefined) {
      lines.push(`Required load: ${results.required_load_kn} kN`);
    }
    if (results.specimen_orientation) lines.push(`Orientation: ${results.specimen_orientation}`);
    if (results.observation) lines.push(`Observation: ${results.observation}`);
    if (results.etchant) lines.push(`Etchant: ${results.etchant}`);
    if (results.reported_conformity) lines.push(`Report conclusion: ${results.reported_conformity}`);

    return lines.length ? lines : [detail?.completed ? "Output could not be extracted automatically." : "Required report not uploaded."];
  };


  const TestChecklist = ({ lab }) => {
    const details = lab?.test_details || lab?.report_details || [];

    if (!details.length) {
      return (
        <div className="test-checklist-empty">
          Detailed test outputs are not available for this saved analysis.
        </div>
      );
    }

    return (
      <div className="test-checklist">
        <div className="test-checklist-header">
          <span>Required Test</span>
          <span>Completion</span>
          <span>Result / Output</span>
          <span>Status</span>
        </div>

        {details.map((detail, index) => (
          <div className="test-checklist-row" key={`${detail.test}-${detail.page_number || "missing"}-${index}`}>
            <div>
              <strong>{formatTestName(detail.test)}</strong>
              {detail.page_number && <small>Report page {detail.page_number}</small>}
            </div>

            <span className={detail.completed ? "completion done" : "completion missing"}>
              {detail.completed ? "Done" : "Not Done"}
            </span>

            <div className="result-output">
              {resultLines(detail).map((line, lineIndex) => (
                <div key={lineIndex}>{line}</div>
              ))}
              {detail.issues?.length > 0 && detail.issues.map((issue, issueIndex) => (
                <div className="result-issue" key={`issue-${issueIndex}`}>{issue}</div>
              ))}
            </div>

            <span className={`status-text ${(detail.status || "review").toLowerCase()}`}>
              {detail.status || "REVIEW"}
            </span>
          </div>
        ))}
      </div>
    );
  };


  return (
    <div className="app">

      {/* SIMPLE HEADER */}
      <header className="header simple-header">
        <div className="simple-header-inner">
          <div className="simple-brand">
            <img className="official-logo" src="/itcpl-logo.png" alt="ITCPL" />
            <div>
             
            </div>
          </div>

          <nav className="top-nav">
            <button
              className={activeView === "analyze" ? "nav-button active" : "nav-button"}
              onClick={() => { setActiveView("analyze"); setSelectedHistoryJob(null); }}
            >
              Analyze Job
            </button>
            <button
              className={activeView === "history" ? "nav-button active" : "nav-button"}
              onClick={() => { setActiveView("history"); setSelectedLab(null); }}
            >
              Job History
            </button>
            <button
              className={activeView === "compliance" ? "nav-button active" : "nav-button"}
              onClick={() => { setActiveView("compliance"); setSelectedLab(null); setSelectedHistoryJob(null); }}
            >
              ISO / NABL
            </button>
          </nav>
        </div>
      </header>

      <main className="container simple-container">
        {/* ANALYZE VIEW */}

        {activeView === "analyze" && (
          <>

            <div className="page-title analyze-title">
              <h2>Analyze New Job</h2>
              <p>Upload documents to validate client requirements against laboratory test reports.</p>
            </div>


            <div className="upload-card">

              <div className="upload-grid">

                <UploadCard
                  step="01"
                  title="Purchase Order"
                  subtitle="Client PO / Offer Letter"
                  file={purchaseOrder}
                  setFile={
                    setPurchaseOrder
                  }
                />


                <UploadCard
                  step="02"
                  title="Job Order"
                  subtitle="ITCPL Job Work Letter"
                  file={jobOrder}
                  setFile={
                    setJobOrder
                  }
                />


                <UploadCard
                  step="03"
                  title="Test Reports"
                  subtitle="Laboratory Test Reports"
                  file={testReports}
                  setFile={
                    setTestReports
                  }
                />

              </div>


              <button
                className="analyze-button"
                disabled={
                  !purchaseOrder ||
                  !jobOrder ||
                  !testReports ||
                  loading
                }
                onClick={
                  analyzeDocuments
                }
              >
                {
                  loading
                    ? "Analyzing Documents..."
                    : "Analyze Documents  →"
                }
              </button>


              {loading && (
                <div className="loading-text">
                  Reading documents and
                  running compliance checks...
                </div>
              )}


              {error && (
                <div className="error-message">
                  {error}
                </div>
              )}

            </div>


            {result && (

              <div className="results-section">

                <div className="result-header">

                  <div>

                    <h2>
                      Analysis Result
                    </h2>

                    <p>
                      {
                        result.customer ||
                        "Unknown Customer"
                      }
                    </p>

                  </div>


                  <div
                    className={
                      `status-badge ${
                        result
                          .saved_job
                          ?.overall_status
                          ?.toLowerCase()
                      }`
                    }
                  >
                    {
                      result
                        .saved_job
                        ?.overall_status
                    }
                  </div>

                </div>


                <div className="job-info">

                  <div>

                    <span>
                      PO Number
                    </span>

                    <strong>
                      {
                        result
                          .purchase_order
                          ?.po_no ||
                        "-"
                      }
                    </strong>

                  </div>


                  <div>

                    <span>
                      Collection Number
                    </span>

                    <strong>
                      {
                        result
                          .job_order
                          ?.collection_no ||
                        "-"
                      }
                    </strong>

                  </div>


                  <div>

                    <span>
                      Job ID
                    </span>

                    <strong>
                      {
                        result
                          .saved_job
                          ?.job_id ||
                        "-"
                      }
                    </strong>

                  </div>

                </div>


                <div className="lab-table">

                  <div className="table-header">

                    <span>
                      Lab No.
                    </span>

                    <span>
                      Heat No.
                    </span>

                    <span>
                      Status
                    </span>

                  </div>


                  {Object.values(
                    result
                      .final_decisions ||
                    {}
                  )
                    .sort(
                      (a, b) =>
                        a
                          .lab_no
                          .localeCompare(
                            b.lab_no
                          )
                    )
                    .map(
                      (lab) => {

                        const jobLab =
                          result
                            .job_order
                            ?.labs
                            ?.find(
                              (item) =>
                                item
                                  .lab_no ===
                                lab.lab_no
                            );

                        const savedLab =
                          result
                            .saved_job_details
                            ?.labs
                            ?.find(
                              (item) =>
                                item
                                  .lab_no ===
                                lab.lab_no
                            );

                        return (

                          <div
                            className="table-row clickable"
                            key={
                              lab.lab_no
                            }
                            onClick={() => {

                              setSelectedLab(
                                getLabDetails(
                                  lab.lab_no
                                )
                              );

                              setReviewNote(
                                ""
                              );

                              setReviewedBy(
                                savedLab
                                  ?.reviewed_by ||
                                "Lab Engineer"
                              );
                            }}
                          >

                            <span>
                              {
                                lab.lab_no
                              }
                            </span>


                            <span>
                              {
                                jobLab
                                  ?.heat_no ||
                                "-"
                              }
                            </span>


                            <span
                              className={
                                `status-text ${
                                  lab
                                    .final_status
                                    .toLowerCase()
                                }`
                              }
                            >
                              {
                                savedLab
                                  ?.review_status
                                  ? `${lab.final_status} / ${savedLab.review_status}`
                                  : lab.final_status
                              }
                            </span>

                          </div>

                        );
                      }
                    )}

                </div>

              </div>

            )}


            {/* LAB DETAILS */}

            {selectedLab && (

              <div className="lab-detail-card">

                <div className="lab-detail-header">

                  <div>

                    <h2>
                      Lab {
                        selectedLab.lab_no
                      }
                    </h2>

                    <p>
                      Heat No: {
                        selectedLab.heat_no
                      }
                    </p>

                  </div>


                  <button
                    className="close-button"
                    onClick={() =>
                      setSelectedLab(
                        null
                      )
                    }
                  >
                    ×
                  </button>

                </div>


                <div
                  className={
                    `large-status ${
                      selectedLab
                        .final_status
                        .toLowerCase()
                    }`
                  }
                >
                  {
                    selectedLab
                      .final_status
                  }
                </div>


                {selectedLab.review_status && (

                  <div
                    className={
                      `manual-review-status ${
                        selectedLab
                          .review_status
                          .toLowerCase()
                      }`
                    }
                  >
                    Manual Review:
                    {" "}
                    {
                      selectedLab
                        .review_status
                    }
                  </div>

                )}


                <div className="detail-section test-results-section">
                  <h3>Required Tests & Test Outputs</h3>
                  <p className="section-help">
                    Every client-required test is listed below. Missing reports are shown as Not Done; completed reports show the extracted test output.
                  </p>
                  <TestChecklist lab={selectedLab} />
                </div>


                <div className="detail-grid">

                  <div className="detail-box">

                    <h3>
                      Required Tests
                    </h3>

                    {
                      selectedLab
                        .required_tests
                        .length > 0
                        ? selectedLab
                            .required_tests
                            .map(
                              (test) => (

                                <p key={test}>
                                  ✓ {
                                    formatTestName(
                                      test
                                    )
                                  }
                                </p>

                              )
                            )
                        : (
                          <p>
                            No required tests found.
                          </p>
                        )
                    }

                  </div>


                  <div className="detail-box">

                    <h3>
                      Uploaded Tests
                    </h3>

                    {
                      selectedLab
                        .uploaded_tests
                        .length > 0
                        ? selectedLab
                            .uploaded_tests
                            .map(
                              (test) => (

                                <p key={test}>
                                  ✓ {
                                    formatTestName(
                                      test
                                    )
                                  }
                                </p>

                              )
                            )
                        : (
                          <p>
                            No reports uploaded.
                          </p>
                        )
                    }

                  </div>

                </div>


                {
                  selectedLab
                    .missing_tests
                    .length > 0 && (

                    <div className="detail-warning">

                      <h3>
                        Missing Tests
                      </h3>

                      {
                        selectedLab
                          .missing_tests
                          .map(
                            (test) => (

                              <p key={test}>
                                • {
                                  formatTestName(
                                    test
                                  )
                                }
                              </p>

                            )
                          )
                      }

                    </div>

                  )
                }


                <div className="detail-section">

                  <h3>
                    Reason
                  </h3>

                  <p>
                    {
                      selectedLab.reason
                    }
                  </p>

                </div>


                <div className="detail-section">

                  <h3>
                    Issues
                  </h3>

                  {
                    selectedLab
                      .issues
                      .length > 0
                      ? selectedLab
                          .issues
                          .map(
                            (
                              issue,
                              index
                            ) => (

                              <div
                                className="issue-item"
                                key={index}
                              >
                                {issue}
                              </div>

                            )
                          )
                      : (
                        <p>
                          No issues detected.
                        </p>
                      )
                  }

                </div>


                <div className="recommended-action">

                  <h3>
                    Recommended Action
                  </h3>

                  <p>
                    {
                      getRecommendedAction(
                        selectedLab
                      )
                    }
                  </p>

                </div>


                {/* MANUAL REVIEW */}

                {
                  selectedLab
                    .final_status ===
                    "REVIEW" && (

                    <div className="manual-review-card">

                      <h3>
                        Manual Review
                      </h3>


                      {
                        selectedLab
                          .review_status && (

                          <div
                            className={
                              `manual-review-status ${
                                selectedLab
                                  .review_status
                                  .toLowerCase()
                              }`
                            }
                          >
                            {
                              selectedLab
                                .review_status
                            }
                          </div>

                        )
                      }


                      {
                        selectedLab
                          .review_status && (

                          <div className="previous-review">

                            <p>
                              <strong>
                                Reviewed By:
                              </strong>
                              {" "}
                              {
                                selectedLab
                                  .reviewed_by ||
                                "-"
                              }
                            </p>


                            <p>
                              <strong>
                                Review Note:
                              </strong>
                              {" "}
                              {
                                selectedLab
                                  .review_note ||
                                "-"
                              }
                            </p>


                            <p>
                              <strong>
                                Reviewed At:
                              </strong>
                              {" "}
                              {
                                formatDate(
                                  selectedLab
                                    .reviewed_at
                                )
                              }
                            </p>

                          </div>

                        )
                      }


                      <label className="review-label">
                        Reviewer
                      </label>


                      <input
                        className="review-input"
                        value={reviewedBy}
                        onChange={(e) =>
                          setReviewedBy(
                            e.target.value
                          )
                        }
                        placeholder="Reviewer name"
                      />


                      <label className="review-label">
                        Review Note
                      </label>


                      <textarea
                        className="review-textarea"
                        value={reviewNote}
                        onChange={(e) =>
                          setReviewNote(
                            e.target.value
                          )
                        }
                        placeholder="Example: Impact test values manually verified from original report."
                      />


                      <div className="review-actions">

                        <button
                          className="approve-button"
                          disabled={
                            reviewDecisionLoading ||
                            !selectedLab.id
                          }
                          onClick={() =>
                            submitManualReview(
                              selectedLab.id,
                              "APPROVED"
                            )
                          }
                        >
                          {
                            reviewDecisionLoading
                              ? "Saving..."
                              : "Approve"
                          }
                        </button>


                        <button
                          className="reject-button"
                          disabled={
                            reviewDecisionLoading ||
                            !selectedLab.id
                          }
                          onClick={() =>
                            submitManualReview(
                              selectedLab.id,
                              "REJECTED"
                            )
                          }
                        >
                          Reject
                        </button>

                      </div>


                      {!selectedLab.id && (

                        <div className="error-message">
                          Lab database ID is unavailable.
                          Re-run the analysis and try again.
                        </div>

                      )}

                    </div>

                  )
                }

              </div>

            )}

          </>
        )}


        {/* JOB HISTORY */}

        {activeView === "history" && (
          <>

            <div className="page-title">

              <h2>
                Job History
              </h2>

              <p>
                View previously analyzed
                compliance jobs.
              </p>

            </div>


            {error && (
              <div className="error-message">
                {error}
              </div>
            )}


            {jobsLoading ? (

              <div className="history-message">
                Loading jobs...
              </div>

            ) : (

              <div className="history-list">

                {
                  jobs.length === 0
                    ? (

                      <div className="history-message">
                        No saved jobs found.
                      </div>

                    )
                    : jobs.map(
                      (job) => (

                        <div
                          className="history-card"
                          key={job.id}
                          onClick={() =>
                            loadHistoryJob(
                              job.id
                            )
                          }
                        >

                          <div>

                            <strong>
                              Job #{job.id}
                            </strong>

                            <span>
                              {
                                job.customer ||
                                "Unknown Customer"
                              }
                            </span>

                          </div>


                          <div>

                            <span>
                              PO Number
                            </span>

                            <strong>
                              {
                                job.po_no ||
                                "-"
                              }
                            </strong>

                          </div>


                          <div>

                            <span>
                              Collection
                            </span>

                            <strong>
                              {
                                job
                                  .collection_no ||
                                "-"
                              }
                            </strong>

                          </div>


                          <div>

                            <span>
                              Labs
                            </span>

                            <strong>
                              {
                                job.lab_count
                              }
                            </strong>

                          </div>


                          <div
                            className={
                              `status-badge ${
                                job
                                  .overall_status
                                  ?.toLowerCase()
                              }`
                            }
                          >
                            {
                              job
                                .overall_status
                            }
                          </div>

                        </div>

                      )
                    )
                }

              </div>

            )}


            {historyLoading && (

              <div className="history-message">
                Loading job details...
              </div>

            )}


            {selectedHistoryJob && (

              <div className="history-detail">

                <div className="result-header">

                  <div>

                    <h2>
                      Job #{
                        selectedHistoryJob.id
                      }
                    </h2>

                    <p>
                      {
                        selectedHistoryJob
                          .customer ||
                        "Unknown Customer"
                      }
                    </p>

                  </div>


                  <div
                    className={
                      `status-badge ${
                        selectedHistoryJob
                          .overall_status
                          ?.toLowerCase()
                      }`
                    }
                  >
                    {
                      selectedHistoryJob
                        .overall_status
                    }
                  </div>

                </div>


                <div className="job-info">

                  <div>

                    <span>
                      PO Number
                    </span>

                    <strong>
                      {
                        selectedHistoryJob
                          .po_no ||
                        "-"
                      }
                    </strong>

                  </div>


                  <div>

                    <span>
                      Collection
                    </span>

                    <strong>
                      {
                        selectedHistoryJob
                          .collection_no ||
                        "-"
                      }
                    </strong>

                  </div>


                  <div>

                    <span>
                      Analyzed
                    </span>

                    <strong className="small-date">
                      {
                        formatDate(
                          selectedHistoryJob
                            .created_at
                        )
                      }
                    </strong>

                  </div>

                </div>


                <div className="lab-table">

                  <div className="table-header">

                    <span>
                      Lab No.
                    </span>

                    <span>
                      Heat No.
                    </span>

                    <span>
                      Status
                    </span>

                  </div>


                  {
                    [
                      ...selectedHistoryJob
                        .labs
                    ]
                      .sort(
                        (a, b) =>
                          a
                            .lab_no
                            .localeCompare(
                              b.lab_no
                            )
                      )
                      .map(
                        (lab) => (

                          <div
                            className="table-row clickable"
                            key={
                              lab.lab_no
                            }
                            onClick={() =>
                              setSelectedHistoryLab(
                                selectedHistoryLab?.lab_no === lab.lab_no
                                  ? null
                                  : lab
                              )
                            }
                          >

                            <span>
                              {
                                lab.lab_no
                              }
                            </span>


                            <span>
                              {
                                lab.heat_no ||
                                "-"
                              }
                            </span>


                            <span
                              className={
                                `status-text ${
                                  lab
                                    .final_status
                                    .toLowerCase()
                                }`
                              }
                            >
                              {
                                lab
                                  .review_status
                                  ? `${lab.final_status} / ${lab.review_status}`
                                  : lab.final_status
                              }
                            </span>

                          </div>

                        )
                      )
                  }

                </div>

                {selectedHistoryLab && (
                  <div className="history-lab-output">
                    <div className="lab-detail-header">
                      <div>
                        <h3>Lab {selectedHistoryLab.lab_no} — Test Outputs</h3>
                        <p>Heat No: {selectedHistoryLab.heat_no || "-"}</p>
                      </div>
                      <button className="close-button" onClick={() => setSelectedHistoryLab(null)}>×</button>
                    </div>
                    <TestChecklist lab={selectedHistoryLab} />
                  </div>
                )}

              </div>

            )}

          </>
        )}


        {/* ISO / NABL COMPLIANCE VIEW */}

        {activeView === "compliance" && (
          <>

            <div className="page-title">
              <h2>
                ISO / NABL Report Compliance
              </h2>

              <p>
                Check report-format and accreditation indicators
                separately from technical PASS / FAIL testing.
              </p>
            </div>


            <div className="upload-card">

              <div
                style={{
                  maxWidth: "560px",
                  margin: "0 auto"
                }}
              >
                <UploadCard
                  title="Test Reports"
                  file={complianceReport}
                  setFile={setComplianceReport}
                />
              </div>


              <button
                className="analyze-button"
                disabled={
                  !complianceReport ||
                  complianceLoading
                }
                onClick={
                  analyzeReportCompliance
                }
              >
                {
                  complianceLoading
                    ? "Checking ISO / NABL Compliance..."
                    : "Check ISO / NABL Compliance"
                }
              </button>


              {complianceLoading && (
                <div className="loading-text">
                  Checking report information, ISO/IEC 17025
                  reporting requirements and NABL indicators...
                </div>
              )}


              {error && (
                <div className="error-message">
                  {error}
                </div>
              )}

            </div>


            {complianceResult && (
              <div className="results-section">

                <div className="result-header">

                  <div>
                    <h2>
                      Report Compliance Result
                    </h2>

                    <p>
                      {complianceResult.standard}
                    </p>
                  </div>

                </div>


                <div className="job-info">

                  <div>
                    <span>
                      ISO 17025 Report Status
                    </span>
                    <strong
                      className={
                        `status-text ${
                          (
                            complianceResult
                              .iso_overall_status ||
                            "review"
                          ).toLowerCase()
                        }`
                      }
                    >
                      {
                        complianceResult
                          .iso_overall_status ||
                        "REVIEW"
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      NABL Scope Status
                    </span>
                    <strong>
                      {
                        complianceResult
                          .nabl_overall_status ||
                        "NOT VERIFIED"
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      Reports Checked
                    </span>
                    <strong>
                      {
                        complianceResult
                          .report_count ||
                        0
                      }
                    </strong>
                  </div>

                </div>


                <div className="detail-section">
                  <h3>
                    What this status means
                  </h3>

                  <p>
                    This page checks report documentation and
                    accreditation indicators only. It does not
                    change technical job PASS, FAIL, MISSING or
                    REVIEW results.
                  </p>

                  <p>
                    {
                      complianceResult
                        .nabl_note
                    }
                  </p>
                </div>


                <div className="lab-table">

                  <div className="table-header">
                    <span>
                      Report / Lab
                    </span>

                    <span>
                      ISO Status
                    </span>

                    <span>
                      NABL Status
                    </span>
                  </div>


                  {
                    (
                      complianceResult
                        .reports ||
                      []
                    ).map(
                      (report, index) => (

                        <div
                          className="table-row clickable"
                          key={
                            `${report.page_number}-${report.document_type}-${index}`
                          }
                          onClick={() =>
                            setSelectedComplianceReport(
                              report
                            )
                          }
                        >

                          <span>
                            {
                              report.report_no ||
                              report.lab_no ||
                              `Page ${report.page_number}`
                            }
                          </span>

                          <span
                            className={
                              `status-text ${
                                (
                                  report
                                    .iso_status ||
                                  "review"
                                ).toLowerCase()
                              }`
                            }
                          >
                            {
                              report
                                .iso_status ||
                              "REVIEW"
                            }
                          </span>

                          <span>
                            {
                              report
                                .nabl_status ||
                              "NOT VERIFIED"
                            }
                          </span>

                        </div>
                      )
                    )
                  }

                </div>

              </div>
            )}


            {selectedComplianceReport && (
              <div className="lab-detail-card">

                <div className="lab-detail-header">

                  <div>
                    <h2>
                      {
                        selectedComplianceReport
                          .report_no ||
                        `Lab ${
                          selectedComplianceReport
                            .lab_no ||
                          "-"
                        }`
                      }
                    </h2>

                    <p>
                      {
                        formatTestName(
                          selectedComplianceReport
                            .document_type
                        )
                      }
                      {" · "}
                      Report page {
                        selectedComplianceReport
                          .page_number
                      }
                    </p>
                  </div>


                  <button
                    className="close-button"
                    onClick={() =>
                      setSelectedComplianceReport(
                        null
                      )
                    }
                  >
                    ×
                  </button>

                </div>


                <div className="job-info">

                  <div>
                    <span>
                      ISO Status
                    </span>
                    <strong
                      className={
                        `status-text ${
                          (
                            selectedComplianceReport
                              .iso_status ||
                            "review"
                          ).toLowerCase()
                        }`
                      }
                    >
                      {
                        selectedComplianceReport
                          .iso_status ||
                        "REVIEW"
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      NABL Status
                    </span>
                    <strong>
                      {
                        selectedComplianceReport
                          .nabl_status ||
                        "NOT VERIFIED"
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      ISO Issues
                    </span>
                    <strong>
                      {
                        selectedComplianceReport
                          .iso_issue_count ||
                        0
                      }
                    </strong>
                  </div>

                </div>


                <div className="detail-section">

                  <h3>
                    ISO/IEC 17025 Report Checks
                  </h3>

                  {
                    (
                      selectedComplianceReport
                        .iso_checks ||
                      []
                    ).map(
                      (check, index) => (

                        <div
                          className="issue-item"
                          key={
                            `${check.code}-${index}`
                          }
                          style={{
                            marginBottom: "12px"
                          }}
                        >

                          <div
                            style={{
                              display: "flex",
                              justifyContent:
                                "space-between",
                              gap: "16px",
                              alignItems:
                                "flex-start"
                            }}
                          >

                            <div>
                              <strong>
                                {check.label}
                              </strong>

                              <div
                                style={{
                                  marginTop: "5px"
                                }}
                              >
                                Clause: {
                                  check.clause ||
                                  "-"
                                }
                              </div>

                              <div
                                style={{
                                  marginTop: "5px"
                                }}
                              >
                                {check.detail}
                              </div>

                              {
                                check.evidence && (
                                  <div
                                    style={{
                                      marginTop:
                                        "5px"
                                    }}
                                  >
                                    Evidence: {
                                      check.evidence
                                    }
                                  </div>
                                )
                              }
                            </div>


                            <span
                              className={
                                `status-text ${
                                  (
                                    check.status ||
                                    "review"
                                  ).toLowerCase()
                                }`
                              }
                            >
                              {
                                check.status ||
                                "REVIEW"
                              }
                            </span>

                          </div>

                        </div>
                      )
                    )
                  }

                </div>


                <div className="detail-section">

                  <h3>
                    NABL Scope Verification
                  </h3>

                  {
                    (
                      selectedComplianceReport
                        .nabl_checks ||
                      []
                    ).length > 0
                      ? (
                          selectedComplianceReport
                            .nabl_checks
                            .map(
                              (check, index) => (
                                <div
                                  className="issue-item"
                                  key={
                                    `nabl-${check.code}-${index}`
                                  }
                                >
                                  <strong>
                                    {check.label}
                                  </strong>

                                  <div
                                    style={{
                                      marginTop: "5px"
                                    }}
                                  >
                                    Status: {
                                      selectedComplianceReport
                                        .nabl_status ||
                                      "NOT VERIFIED"
                                    }
                                  </div>

                                  <div
                                    style={{
                                      marginTop: "5px"
                                    }}
                                  >
                                    {check.detail}
                                  </div>

                                  {
                                    check.evidence && (
                                      <div
                                        style={{
                                          marginTop: "5px"
                                        }}
                                      >
                                        Evidence: {
                                          check.evidence
                                        }
                                      </div>
                                    )
                                  }
                                </div>
                              )
                            )
                        )
                      : (
                          <p>
                            NABL scope could not be matched reliably from this report.
                          </p>
                        )
                  }

                </div>


                <div className="recommended-action">
                  <h3>
                    Important
                  </h3>

                  <p>
                    NABL REVIEW does not mean the test failed.
                    It means current accreditation/scope could
                    not be independently verified from this
                    report alone.
                  </p>
                </div>

              </div>
            )}

          </>
        )}

      </main>

    </div>
  );
}

export default App;