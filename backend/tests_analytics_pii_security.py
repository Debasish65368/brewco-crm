import asyncio
import json
from unittest.mock import patch, MagicMock

# Import the function that sends data to Groq
from clients.ai_client import generate_sql_summary

async def test_pii_sanitization():
    # Mock data that simulates a database result somehow containing PII
    mock_db_results = [
        {
            "name": "Test User",
            "email": "test@example.invalid",
            "phone": "0000000000",
            "city": "Delhi",
            "total_spent": 5000,
            "order_count": 5
        },
        {
            "name": "Another User",
            "email": "another@example.invalid",
            "phone": "1111111111",
            "city": "Mumbai",
            "total_spent": 12000,
            "order_count": 12
        }
    ]
    
    question = "Who are the top spenders?"
    
    # We patch the Groq client creation inside generate_sql_summary
    # Specifically, we want to intercept what gets passed to groq_client.chat.completions.create
    with patch("clients.ai_client.groq_client.chat.completions.create") as mock_create:
        # Mock the response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Summary"
        mock_create.return_value = mock_response
        
        await generate_sql_summary(question, mock_db_results)
        
        # Check the payload sent to Groq
        assert mock_create.called, "Groq API was not called"
        call_args = mock_create.call_args
        messages = call_args[1]["messages"]
        prompt_content = messages[0]["content"]
        
        # Assert PII was stripped
        assert "Test User" not in prompt_content, "PII leaked: name 'Test User'"
        assert "test@example.invalid" not in prompt_content, "PII leaked: email"
        assert "0000000000" not in prompt_content, "PII leaked: phone"
        
        assert "Another User" not in prompt_content, "PII leaked: name 'Another User'"
        assert "another@example.invalid" not in prompt_content, "PII leaked: email"
        assert "1111111111" not in prompt_content, "PII leaked: phone"
        
        # Assert non-PII is preserved
        assert "Delhi" in prompt_content, "Non-PII lost: city 'Delhi'"
        assert "5000" in prompt_content, "Non-PII lost: total_spent '5000'"
        assert "Mumbai" in prompt_content, "Non-PII lost: city 'Mumbai'"
        assert "12000" in prompt_content, "Non-PII lost: total_spent '12000'"
        
        print("[PASS] AI Analytics payload verification: PII fields (name, email, phone) were successfully blocked from reaching Groq.")

if __name__ == "__main__":
    print("Running Analytics PII Security Test...")
    asyncio.run(test_pii_sanitization())
