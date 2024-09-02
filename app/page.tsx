"use client";

import { useState, useRef, useEffect } from "react";

export default function Home() { 
  const [file, setFile] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<
    Array<{ role: string; content: string }>
  >([]);
  const [inputMessage, setInputMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch("/api/start_chat", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setSessionId(data.session_id);
      setMessages([
        {
          role: "assistant",
          content: `Chat session started for file: ${selectedFile.name}. How can I help you?`,
        },
      ]);
    } catch (error) {
      console.error("Error:", error);
      setError("Failed to start chat session. Please try again.");
      setFile(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || !sessionId) return;

    setMessages((prev) => [...prev, { role: "user", content: inputMessage }]);
    setInputMessage("");
    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("message", inputMessage);

    try {
      const response = await fetch(`/api/chat/${sessionId}`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response },
      ]);
    } catch (error) {
      console.error("Error:", error);
      setError("Failed to send message. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleEndChat = async () => {
    if (!sessionId) return;

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/end_chat/${sessionId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      setSessionId(null);
      setMessages([]);
      setFile(null);
    } catch (error) {
      console.error("Error ending chat:", error);
      setError("Failed to end chat session. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="p-4 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Chat with Document</h1>
      {error && (
        <div
          className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4"
          role="alert"
        >
          <span className="block sm:inline">{error}</span>
        </div>
      )}
      {!sessionId ? (
        <div className="mb-4">
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            className="mb-2"
          />
          {loading && <p>Starting chat session...</p>}
          {file && <p>Selected file: {file.name}</p>}
        </div>
      ) : (
        <>
          <div
            ref={chatContainerRef}
            className="border rounded-lg p-4 h-96 overflow-y-auto mb-4"
          >
            {messages.map((message, index) => (
              <div
                key={index}
                className={`mb-2 ${
                  message.role === "user" ? "text-right" : "text-left"
                }`}
              >
                <span
                  className={`inline-block p-2 rounded-lg ${
                    message.role === "user"
                      ? "bg-blue-500 text-white"
                      : "bg-neutral-500 text-white"
                  }`}
                >
                  {message.content}
                </span>
              </div>
            ))}
          </div>
          <form onSubmit={handleSendMessage} className="flex mb-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              className="flex-grow border rounded-l-lg p-2"
              placeholder="Type your message..."
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-500 text-white px-4 py-2 rounded-r-lg disabled:bg-blue-300"
            >
              Send
            </button>
          </form>
          <button
            onClick={handleEndChat}
            disabled={loading}
            className="bg-red-500 text-white px-4 py-2 rounded-lg w-full disabled:bg-red-300"
          >
            End Chat
          </button>
          {loading && <p className="mt-2">Processing...</p>}
        </>
      )}
    </main>
  );
}
