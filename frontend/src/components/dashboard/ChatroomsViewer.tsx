import { useEffect, useRef, useState } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { 
  MessageSquare, 
  Send, 
  RefreshCw, 
  Bot, 
  User, 
  ArrowRight, 
  Brain, 
  Activity,
  UserCheck
} from 'lucide-react';

export function ChatroomsViewer() {
  const currentOrgSlug = useAgentStore((state) => state.currentOrgSlug);
  const chats = useAgentStore((state) => state.chats);
  const fetchChats = useAgentStore((state) => state.fetchChats);
  const activeChatroomId = useAgentStore((state) => state.activeChatroomId);
  const setActiveChatroomId = useAgentStore((state) => state.setActiveChatroomId);
  const activeChatMessages = useAgentStore((state) => state.activeChatMessages);
  const fetchChatMessages = useAgentStore((state) => state.fetchChatMessages);
  const isFetchingMessages = useAgentStore((state) => state.isFetchingMessages);

  const [inputMessage, setInputMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Poll chats list on mount and periodically
  useEffect(() => {
    fetchChats();
    const interval = setInterval(() => {
      fetchChats();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-select first chatroom if none selected
  useEffect(() => {
    if (chats.length > 0 && !activeChatroomId) {
      setActiveChatroomId(chats[0].band_room_id);
    }
  }, [chats, activeChatroomId]);

  // Poll active chatroom messages
  useEffect(() => {
    if (!activeChatroomId) return;
    
    // Fetch immediately
    fetchChatMessages(activeChatroomId);

    const interval = setInterval(() => {
      fetchChatMessages(activeChatroomId);
    }, 3000);

    return () => clearInterval(interval);
  }, [activeChatroomId]);

  // Auto scroll to bottom when messages list changes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeChatMessages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || !activeChatroomId) return;

    setIsSending(true);

    try {
      const targetUrl = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/orgs/${currentOrgSlug}/agents/chats/${activeChatroomId}/messages`;
      const res = await fetch(targetUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: inputMessage.trim() })
      });
      if (res.ok) {
        setInputMessage('');
        // Refresh messages immediately
        await fetchChatMessages(activeChatroomId);
      }
    } catch (err) {
      console.error("Failed to send message", err);
    } finally {
      setIsSending(false);
    }
  };

  const selectedChat = chats.find(c => c.band_room_id === activeChatroomId) || chats[0];

  // Helper to parse message content and check if it is JSON agent handoff
  const parseMessageContent = (content: string) => {
    try {
      const parsed = JSON.parse(content);
      if (parsed && typeof parsed === 'object' && 'from_role' in parsed && 'to_role' in parsed) {
        return {
          isJson: true,
          fromRole: parsed.from_role,
          toRole: parsed.to_role,
          message: parsed.message
        };
      }
    } catch (e) {
      // not a json string
    }
    return { isJson: false, raw: content };
  };

  // Helper to get matching avatar styles
  const getRoleTheme = (role: string) => {
    const r = role.toLowerCase();
    if (r === 'planner' || r === 'ceo' || r === 'plan') {
      return {
        bg: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
        badgeBg: 'bg-purple-500 text-white',
        border: 'border-purple-500/30',
        name: 'Planner Agent'
      };
    }
    if (r === 'engineer' || r === 'developer' || r === 'eng') {
      return {
        bg: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
        badgeBg: 'bg-emerald-500 text-white',
        border: 'border-emerald-500/30',
        name: 'Developer Agent'
      };
    }
    if (r === 'reviewer' || r === 'audit' || r === 'rev') {
      return {
        bg: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
        badgeBg: 'bg-amber-500 text-white',
        border: 'border-amber-500/30',
        name: 'Reviewer Agent'
      };
    }
    if (r === 'tester' || r === 'qa' || r === 'tst') {
      return {
        bg: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
        badgeBg: 'bg-orange-500 text-white',
        border: 'border-orange-500/30',
        name: 'QA Tester Agent'
      };
    }
    return {
      bg: 'bg-slate-500/10 text-slate-600 border-slate-500/20',
      badgeBg: 'bg-slate-500 text-white',
      border: 'border-slate-500/30',
      name: role
    };
  };

  // Determine active roles in current chat history
  const activeRolesInHistory = new Set<string>();
  activeChatMessages.forEach(m => {
    const parsed = parseMessageContent(m.content);
    if (parsed.isJson) {
      if (parsed.fromRole) activeRolesInHistory.add(parsed.fromRole.toLowerCase());
      if (parsed.toRole) activeRolesInHistory.add(parsed.toRole.toLowerCase());
    } else {
      const name = m.sender_name?.toLowerCase() || '';
      if (name.includes('plan')) activeRolesInHistory.add('planner');
      if (name.includes('eng') || name.includes('dev')) activeRolesInHistory.add('engineer');
      if (name.includes('rev')) activeRolesInHistory.add('reviewer');
      if (name.includes('test') || name.includes('tst') || name.includes('qa')) activeRolesInHistory.add('tester');
    }
  });

  return (
    <div className="flex-1 flex overflow-hidden h-[calc(100vh-64px)] bg-background">
      {/* 1. Left Sidebar - Chatrooms List */}
      <div className="w-80 border-r border-border bg-card flex flex-col shrink-0">
        <div className="p-4 border-b border-border flex justify-between items-center bg-secondary/30">
          <div>
            <h2 className="font-bold text-foreground flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-primary" />
              Band Chatrooms
            </h2>
            <p className="text-[11px] text-muted-foreground mt-0.5">Active rooms running on Band mesh</p>
          </div>
          <button 
            onClick={() => fetchChats()} 
            className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground transition-colors"
            title="Refresh Chats"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetchingMessages ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {chats.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-xs">
              No active chat rooms found.
            </div>
          ) : (
            chats.map((chat) => {
              const isSelected = chat.band_room_id === activeChatroomId;
              const isMock = chat.band_room_id.startsWith('band-mock-');

              return (
                <button
                  key={chat.band_room_id}
                  onClick={() => setActiveChatroomId(chat.band_room_id)}
                  className={`w-full text-left p-3.5 rounded-lg border transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md flex flex-col gap-1.5 ${
                    isSelected 
                      ? 'bg-primary/5 border-primary shadow-sm' 
                      : 'bg-card border-border hover:bg-secondary/40'
                  }`}
                >
                  <div className="flex justify-between items-start w-full">
                    <span className="font-semibold text-sm text-foreground line-clamp-1 flex-1">{chat.title}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ml-2 shrink-0 ${
                      chat.status === 'COMPLETED' 
                        ? 'bg-emerald-500/10 text-emerald-600' 
                        : 'bg-amber-500/10 text-amber-600 animate-pulse'
                    }`}>
                      {chat.status}
                    </span>
                  </div>

                  <p className="text-xs text-muted-foreground line-clamp-2">{chat.description}</p>
                  
                  <div className="flex items-center justify-between mt-1 text-[10px] text-muted-foreground/80 font-mono">
                    <span>ID: {chat.band_room_id.slice(0, 14)}...</span>
                    {isMock && (
                      <span className="bg-slate-500/10 text-slate-500 px-1.5 py-0.5 rounded text-[9px] font-bold font-sans">OFFLINE DEMO</span>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* 2. Main Chat Area */}
      {selectedChat ? (
        <div className="flex-1 flex flex-col bg-background overflow-hidden">
          {/* Header Panel - Participants Flow */}
          <div className="p-4 border-b border-border bg-card flex flex-col md:flex-row md:items-center justify-between gap-4 shrink-0 shadow-sm z-10">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-foreground text-base">{selectedChat.title}</h3>
                <span className="text-[10px] font-mono bg-secondary text-muted-foreground px-2 py-0.5 rounded border border-border">
                  {selectedChat.band_room_id}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">{selectedChat.description}</p>
            </div>

            {/* Premium Participant Flow Diagram */}
            <div className="flex items-center gap-1.5 bg-secondary/30 p-2 rounded-lg border border-border/60 self-start md:self-auto overflow-x-auto max-w-full">
              {/* Planner Node */}
              <div className={`flex items-center gap-1 px-2.5 py-1 rounded-md border text-xs font-bold transition-all ${
                activeRolesInHistory.has('planner') 
                  ? 'bg-purple-500/10 text-purple-600 border-purple-500/30 shadow-sm' 
                  : 'bg-card text-muted-foreground/60 border-border/40'
              }`}>
                <Bot className="w-3.5 h-3.5" />
                <span>Planner</span>
              </div>

              <ArrowRight className="w-3 h-3 text-muted-foreground/40 shrink-0" />

              {/* Developer Node */}
              <div className={`flex items-center gap-1 px-2.5 py-1 rounded-md border text-xs font-bold transition-all ${
                activeRolesInHistory.has('engineer') 
                  ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30 shadow-sm' 
                  : 'bg-card text-muted-foreground/60 border-border/40'
              }`}>
                <Bot className="w-3.5 h-3.5" />
                <span>Developer</span>
              </div>

              <ArrowRight className="w-3 h-3 text-muted-foreground/40 shrink-0" />

              {/* Reviewer Node */}
              <div className={`flex items-center gap-1 px-2.5 py-1 rounded-md border text-xs font-bold transition-all ${
                activeRolesInHistory.has('reviewer') 
                  ? 'bg-amber-500/10 text-amber-600 border-amber-500/30 shadow-sm' 
                  : 'bg-card text-muted-foreground/60 border-border/40'
              }`}>
                <Bot className="w-3.5 h-3.5" />
                <span>Reviewer</span>
              </div>

              <ArrowRight className="w-3 h-3 text-muted-foreground/40 shrink-0" />

              {/* Tester Node */}
              <div className={`flex items-center gap-1 px-2.5 py-1 rounded-md border text-xs font-bold transition-all ${
                activeRolesInHistory.has('tester') 
                  ? 'bg-orange-500/10 text-orange-600 border-orange-500/30 shadow-sm' 
                  : 'bg-card text-muted-foreground/60 border-border/40'
              }`}>
                <Bot className="w-3.5 h-3.5" />
                <span>QA Tester</span>
              </div>
            </div>
          </div>

          {/* Conversation Speech Timeline */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-secondary/10">
            {activeChatMessages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground/80 py-12">
                <Activity className="w-10 h-10 mb-3 text-primary animate-pulse" />
                <span className="font-semibold text-foreground">Listening to Chatroom logs...</span>
                <p className="text-xs mt-2 max-w-sm">No messages or handoff packets recorded in this room yet.</p>
              </div>
            ) : (
              activeChatMessages.map((msg) => {
                const parsed = parseMessageContent(msg.content);
                const isHuman = msg.sender_type === 'human';

                if (isHuman) {
                  // Render Human Developer message bubble on the right side
                  return (
                    <div key={msg.id} className="flex justify-end items-start gap-3 w-full">
                      <div className="max-w-[70%]">
                        <div className="flex items-center justify-end gap-2 mb-1.5">
                          <span className="text-[11px] text-muted-foreground">
                            {msg.inserted_at ? new Date(msg.inserted_at).toLocaleTimeString() : ''}
                          </span>
                          <span className="text-xs font-bold text-foreground">Developer (Human)</span>
                        </div>
                        <div className="bg-primary text-primary-foreground p-3.5 rounded-2xl rounded-tr-none shadow-sm text-sm border border-primary/20">
                          {msg.content}
                        </div>
                      </div>
                      <div className="w-9 h-9 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0 shadow-sm">
                        <User className="w-4 h-4" />
                      </div>
                    </div>
                  );
                }

                if (parsed.isJson) {
                  // Render Agent-to-Agent Handoff Card
                  const fromTheme = getRoleTheme(parsed.fromRole);
                  const toTheme = getRoleTheme(parsed.toRole);

                  return (
                    <div key={msg.id} className="flex justify-start gap-4 items-start w-full">
                      {/* Left side avatar - sender */}
                      <div className={`w-9 h-9 rounded-full ${fromTheme.bg} border flex items-center justify-center font-bold text-xs shrink-0 shadow-sm`}>
                        <Bot className="w-4 h-4" />
                      </div>

                      <div className="flex-1 max-w-[80%]">
                        {/* Title handoff badge */}
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${fromTheme.badgeBg}`}>
                            {fromTheme.name}
                          </span>
                          <ArrowRight className="w-3 h-3 text-muted-foreground" />
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${toTheme.badgeBg}`}>
                            {toTheme.name}
                          </span>
                          <span className="text-[11px] text-muted-foreground ml-auto">
                            {msg.inserted_at ? new Date(msg.inserted_at).toLocaleTimeString() : ''}
                          </span>
                        </div>

                        {/* Speech Bubble / Codeblock Card */}
                        <div className="bg-card border border-border rounded-xl p-4 shadow-sm hover:shadow-md hover:border-border/80 transition-all duration-200">
                          <div className="text-xs font-mono text-muted-foreground uppercase border-b border-border pb-1.5 mb-2 tracking-wider">
                            Packet Payload (Command: {parsed.message.cmd || 'N/A'})
                          </div>

                          <div className="text-sm text-foreground font-mono bg-secondary/35 p-3 rounded border border-border/40 overflow-x-auto">
                            {parsed.message.task && (
                              <div>
                                <span className="text-blue-500 font-bold">Task:</span> {parsed.message.task}
                              </div>
                            )}
                            {parsed.message.report && (
                              <div>
                                <span className="text-emerald-500 font-bold">Report:</span> {parsed.message.report}
                              </div>
                            )}
                            {parsed.message.message && (
                              <div>
                                <span className="text-purple-500 font-bold">Message:</span> {parsed.message.message}
                              </div>
                            )}
                            {!parsed.message.task && !parsed.message.report && !parsed.message.message && (
                              JSON.stringify(parsed.message, null, 2)
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                }

                // Render logs / thoughts / actions
                const senderRole = msg.sender_name?.toLowerCase().includes('plan') ? 'planner' :
                                   msg.sender_name?.toLowerCase().includes('eng') ? 'engineer' :
                                   msg.sender_name?.toLowerCase().includes('rev') ? 'reviewer' :
                                   msg.sender_name?.toLowerCase().includes('test') ? 'tester' : 'other';
                const roleTheme = getRoleTheme(senderRole);
                const isThought = msg.message_type === 'thought';
                const isAction = msg.message_type === 'action';

                return (
                  <div key={msg.id} className="flex justify-start gap-4 items-start w-full">
                    {/* Left avatar */}
                    <div className={`w-9 h-9 rounded-full ${roleTheme.bg} border flex items-center justify-center font-bold text-xs shrink-0 shadow-sm`}>
                      {isThought ? <Brain className="w-4 h-4 text-purple-500 animate-pulse" /> : <Bot className="w-4 h-4" />}
                    </div>

                    <div className="flex-1 max-w-[80%]">
                      {/* Name / Date */}
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-foreground">{msg.sender_name || roleTheme.name}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                          isThought 
                            ? 'bg-purple-500/10 text-purple-600' 
                            : isAction 
                              ? 'bg-blue-500/10 text-blue-600' 
                              : 'bg-slate-500/10 text-slate-600'
                        }`}>
                          {msg.message_type || 'event'}
                        </span>
                        <span className="text-[11px] text-muted-foreground ml-auto">
                          {msg.inserted_at ? new Date(msg.inserted_at).toLocaleTimeString() : ''}
                        </span>
                      </div>

                      {/* Bubble */}
                      <div className={`p-3.5 rounded-2xl rounded-tl-none shadow-sm text-sm border ${
                        isThought 
                          ? 'bg-purple-500/[0.02] border-purple-500/20 text-purple-900 dark:text-purple-200' 
                          : isAction 
                            ? 'bg-blue-500/[0.02] border-blue-500/20 text-blue-900 dark:text-blue-200' 
                            : 'bg-card border-border text-foreground'
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={chatEndRef} />
          </div>

          {/* 3. Footer Pane - Human Injection Input */}
          <div className="p-4 border-t border-border bg-card shadow-sm shrink-0">
            <form onSubmit={handleSendMessage} className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  placeholder="Inject developer message / command feedback to Band Mesh..."
                  className="w-full pl-4 pr-12 py-3 rounded-xl border border-border bg-background text-foreground text-sm outline-none focus:ring-2 focus:ring-primary/20 transition-all duration-200 shadow-inner"
                  disabled={isSending}
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  <span className="text-[9px] font-bold text-muted-foreground bg-secondary px-1.5 py-0.5 rounded border border-border flex items-center gap-1 select-none">
                    <UserCheck className="w-2.5 h-2.5 text-primary" />
                    Human
                  </span>
                </div>
              </div>
              <button
                type="submit"
                disabled={isSending || !inputMessage.trim()}
                className="px-5 py-3 rounded-xl bg-primary text-primary-foreground hover:bg-primary/95 transition-all text-sm font-bold flex items-center gap-2 shadow-sm disabled:opacity-50 disabled:pointer-events-none hover:shadow active:scale-95"
              >
                {isSending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                <span>Send</span>
              </button>
            </form>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-center text-muted-foreground p-8 bg-secondary/15">
          <MessageSquare className="w-12 h-12 mb-3 text-muted-foreground/60 animate-bounce" />
          <h3 className="text-lg font-bold text-foreground">No Room Selected</h3>
          <p className="text-sm mt-1 max-w-sm">Please select or start a task in the active workspace to view its Band chatroom dialogs.</p>
        </div>
      )}
    </div>
  );
}
