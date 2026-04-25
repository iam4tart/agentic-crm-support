import sys
import os
import uuid


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

def run_test_case(name, messages, thread_id=None):
    """Runs a standard test case without manual approval loops."""
    print(f"\n>>> Running Test: {name}")
    t_id = thread_id if thread_id else f"test_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": t_id}}
    
    state_output = None
    for msg in messages:
        print(f"Input: {msg}")
        
        state_output = app.invoke(
            {"messages": [msg], "ticket_data": {}, "next_step": ""}, 
            config=config
        )
        
    final_message = state_output["messages"][-1]
    
    content = final_message.content if hasattr(final_message, 'content') else str(final_message)
    
    print(f"Final Agent Response: {content.strip()[:150]}...") 
    return content

def run_test_case_with_approval(name, messages):
    """Runs a test case that pauses for user input before executing tools."""
    print(f"\n>>> Running Test: {name}")
    t_id = f"approve_test_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": t_id}}
    
    for msg in messages:
        print(f"Input: {msg}")
        app.invoke({"messages": [msg], "ticket_data": {}, "next_step": ""}, config=config)
        
        
        snapshot = app.get_state(config)
        
        while snapshot.next:
            if "action" in snapshot.next:
                
                last_msg = snapshot.values['messages'][-1]
                tool_calls = getattr(last_msg, 'tool_calls', 'No tool calls found')
                
                print(f"\n PAUSED: Tool Execution Pending.")
                print(f"Proposed Action: {tool_calls}")
                
                user_approval = input("Proceed with tool execution? (y/n): ")
                
                if user_approval.lower() == 'y':
                    print("--- Approval Granted. Resuming... ---")
                    
                    app.invoke(None, config=config) 
                    snapshot = app.get_state(config)
                else:
                    print("--- Action Denied. Stopping this test branch. ---")
                    return "Action Denied"

    final_state = app.get_state(config)
    final_resp = final_state.values["messages"][-1]
    content = final_resp.content if hasattr(final_resp, 'content') else str(final_resp)
    return content

def test_identity_recall():
    resp = run_test_case("Identity", ["My name is Aarush", "What is my name?"])
    assert "Aarush" in resp, "Identity Recall Failed."
    print("✅ Identity Recall Passed!")

def test_context_switch():
    messages = ["How do I recover my password?", "Also, can you help me check my last invoice?"]
    resp = run_test_case("Context Switch", messages)
    assert "invoice" in resp.lower() or "billing" in resp.lower(), "Context Switch Failed."
    print("✅ Context Switch Passed!")

if __name__ == "__main__":
    try:
        test_identity_recall()
        test_context_switch()
        
        print("\n>>> Testing Tool Execution with Manual Approval")
        
        approval_msg = ["My name is Aarush. Please reset my password for aarush@test.com"]
        h_resp = run_test_case_with_approval("Manual Approval", approval_msg)
        
        print(f"\nFinal Agent Output: {h_resp}")
        print("\n ALL SYSTEMS OPERATIONAL")
        
    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")