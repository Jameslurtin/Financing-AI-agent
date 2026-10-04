const form = document.querySelector('#assessment-form');
const fields = document.querySelector('#form-fields');
const errorBox = document.querySelector('#form-error');
const resultPanel = document.querySelector('.result-panel');
const badge = document.querySelector('#result-badge');
const examples = document.querySelectorAll('[data-example]');
let report = null;
const euro = value => new Intl.NumberFormat('en-IE', {style: 'currency', currency: 'EUR', maximumFractionDigits: 2}).format(value);
const setText = (id, text) => { document.getElementById(id).textContent = text; };
const modes = {gemini_explanation: 'Gemini assessment with a controlled explanation', gemini_tool_calling: 'Gemini tool calling completed', review_without_llm: 'Review required — no AI call needed', deterministic_fallback: 'Deterministic fallback'};

examples.forEach(button => button.addEventListener('click', () => {
  const values = {company_name: 'ABC Software', industry: 'Technology', annual_revenue: 100000, employees: 8, requested_amount: button.dataset.example === 'review' ? 50000 : 20000, financing_purpose: button.dataset.example === 'invoice' ? 'Improve short-term cash flow from unpaid invoices' : 'Buy new equipment'};
  Object.entries(values).forEach(([name, value]) => { form.elements[name].value = value; });
  errorBox.hidden = true;
  invalidateResult();
}));

function invalidateResult() {
  if (report) {
    report = null;
    document.querySelector('#result-content').hidden = true;
    document.querySelector('#empty-state').hidden = false;
    badge.textContent = 'Ready for a new assessment';
    badge.className = 'badge';
  }
}
form.addEventListener('input', invalidateResult);

function renderResult(data, request) {
  report = {request, assessment: data, assessed_at: new Date().toISOString()};
  const review = data.requires_human_review;
  const ratio = request.requested_amount / request.annual_revenue * 100;
  badge.textContent = review ? 'Human review needed' : 'Potential match';
  badge.className = `badge ${review ? 'review' : 'success'}`;
  setText('result-company', data.company);
  setText('result-category', data.recommended_financing || 'Let’s take a closer look.');
  setText('result-status', data.status);
  setText('result-amount', euro(request.requested_amount));
  setText('result-ratio', `${new Intl.NumberFormat('en', {maximumFractionDigits: 1}).format(ratio)}%`);
  setText('threshold-value', euro(request.annual_revenue * 0.3));
  document.querySelector('#meter-fill').style.width = `${Math.min(ratio, 100)}%`;
  document.querySelector('#meter-fill').style.background = review ? '#c8a363' : '#83a268';
  setText('result-explanation', data.ai_explanation);
  document.querySelector('#fallback-notice').hidden = !data.llm_fallback;
  document.querySelector('#review-notice').hidden = !review;
  setText('detail-workflow', data.workflow === 'agentic' ? 'AI agent' : 'Guided assessment');
  setText('detail-execution', modes[data.execution_mode] || data.execution_mode);
  setText('detail-tools', data.tool_calls.length ? data.tool_calls.join(' → ') : 'No agent tool calls observed.');
  document.querySelector('#result-content').hidden = false;
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  const values = new FormData(form);
  const request = Object.fromEntries(['company_name', 'industry', 'financing_purpose'].map(key => [key, values.get(key).trim()]));
  ['annual_revenue', 'employees', 'requested_amount'].forEach(key => { request[key] = Number(values.get(key)); });
  if (Object.values(request).some(value => value === '' || (typeof value === 'number' && (!Number.isFinite(value) || value <= 0)))) {
    errorBox.textContent = 'Please complete all fields with valid, positive values.';
    errorBox.hidden = false;
    return;
  }
  const agentic = values.get('workflow') === 'agentic';
  report = null;
  errorBox.hidden = true;
  fields.disabled = true;
  examples.forEach(button => { button.disabled = true; });
  resultPanel.setAttribute('aria-busy', 'true');
  document.querySelector('#empty-state').hidden = true;
  document.querySelector('#result-content').hidden = true;
  document.querySelector('#loading-state').hidden = false;
  badge.textContent = 'Assessment in progress';
  badge.className = 'badge';
  setText('loading-message', agentic ? 'Asking Gemini to check your request using the available tools…' : 'Checking eligibility and preparing your explanation…');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 240000);
  try {
    const response = await fetch(agentic ? '/agent-evaluate' : '/evaluate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(request), signal: controller.signal});
    if (!response.ok) {
      let message = 'The assessment could not be completed. Please try again.';
      if (response.status === 422) {
        const problem = await response.json();
        message = Array.isArray(problem.detail) ? problem.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join('; ') : 'Please check your input.';
      }
      throw new Error(message);
    }
    const data = await response.json();
    if (!data.eligibility || typeof data.requires_human_review !== 'boolean' || !Array.isArray(data.tool_calls) || typeof data.ai_explanation !== 'string') throw new Error('The server returned an incomplete assessment. Please try again.');
    renderResult(data, request);
    if (window.matchMedia('(max-width: 650px)').matches) resultPanel.scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) {
    errorBox.textContent = error.name === 'AbortError' ? 'This request took too long. Please retry the guided assessment.' : error instanceof TypeError ? 'Cannot reach the application. Check that the FastAPI server is running and try again.' : error.message;
    errorBox.hidden = false;
    document.querySelector('#empty-state').hidden = false;
    badge.textContent = 'Please try again';
  } finally {
    clearTimeout(timeout);
    fields.disabled = false;
    examples.forEach(button => { button.disabled = false; });
    document.querySelector('#loading-state').hidden = true;
    resultPanel.setAttribute('aria-busy', 'false');
  }
});

document.querySelector('#download-button').addEventListener('click', () => {
  if (!report) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'financing-assessment.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
