const API_BASE =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const token = localStorage.getItem("pa_token");

  const headers = {
    Accept: "application/json",
    ...(options.headers || {})
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const isFormData = options.body instanceof FormData;

  if (!isFormData && options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers
    });
  } catch (error) {
    const connectionError = new Error(
      `Cannot connect to the backend at ${API_BASE}. Start FastAPI on port 8000 and try again.`
    );

    connectionError.cause = error;
    connectionError.code = "BACKEND_UNREACHABLE";

    throw connectionError;
  }

  const text = await response.text();

  let data = null;

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    if (data?.detail) {
      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail
          .map((item) => item.msg || JSON.stringify(item))
          .join(", ");
      }
    } else if (typeof data === "string" && data.trim()) {
      message = data;
    }

    const error = new Error(message);
    error.status = response.status;
    error.data = data;

    throw error;
  }

  return data;
}

export const api = {
  get(path) {
    return request(path, {
      method: "GET"
    });
  },

  post(path, body) {
    return request(path, {
      method: "POST",
      body: JSON.stringify(body)
    });
  },

  patch(path, body) {
    return request(path, {
      method: "PATCH",
      body: JSON.stringify(body)
    });
  },

  put(path, body) {
    return request(path, {
      method: "PUT",
      body: JSON.stringify(body)
    });
  },

  delete(path) {
    return request(path, {
      method: "DELETE"
    });
  },

  upload(path, file, fieldName = "file") {
    const formData = new FormData();
    formData.append(fieldName, file);

    return request(path, {
      method: "POST",
      body: formData
    });
  },

  baseUrl: API_BASE
};