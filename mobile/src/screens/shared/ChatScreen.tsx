import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';
import { MessageOut } from '../../api/types';

export function ChatScreen({ route }: { route: { params: { threadId: string } } }) {
  const { threadId } = route.params;
  const { authedApi, state } = useAuth();
  const myUserId = state.status === 'signedIn' ? state.claims.sub : null;
  const [messages, setMessages] = useState<MessageOut[] | null>(null);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setMessages(await authedApi<MessageOut[]>(`/messages/threads/${threadId}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load this conversation.');
    }
  }, [authedApi, threadId]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const send = async () => {
    if (!draft.trim()) return;
    setSending(true);
    try {
      const sent = await authedApi<MessageOut>('/messages', { method: 'POST', body: { thread_id: threadId, content: draft } });
      setMessages((prev) => [...(prev ?? []), sent]);
      setDraft('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not send that message.');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B2A45" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.errorBar}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}
      <FlatList
        data={messages ?? []}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => {
          const mine = item.sender_user_id === myUserId;
          return (
            <View style={[styles.bubble, mine ? styles.mine : styles.theirs]}>
              <Text style={mine ? styles.mineText : styles.theirsText}>{item.content}</Text>
              {item.is_flagged ? (
                <Text style={styles.flagText} testID={`flag-${item.id}`}>
                  ⚠ This message may reference off-platform contact
                </Text>
              ) : null}
            </View>
          );
        }}
      />
      <View style={styles.composeRow}>
        <TextInput
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder="Type a message…"
          testID="chat-input"
        />
        <TouchableOpacity style={styles.sendButton} onPress={send} disabled={sending} testID="chat-send">
          <Text style={styles.sendButtonText}>Send</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F6F3EC' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F6F3EC' },
  errorBar: { backgroundColor: '#FFFDF8', padding: 10 },
  errorText: { color: '#A6452F' },
  list: { padding: 12 },
  bubble: { maxWidth: '80%', borderRadius: 10, padding: 10, marginBottom: 8 },
  mine: { backgroundColor: '#1B2A45', alignSelf: 'flex-end' },
  theirs: { backgroundColor: '#FFFDF8', borderWidth: 1, borderColor: '#DDD6C7', alignSelf: 'flex-start' },
  mineText: { color: '#FFFDF8' },
  theirsText: { color: '#1B2A45' },
  flagText: { color: '#A6452F', fontSize: 11, marginTop: 6 },
  composeRow: { flexDirection: 'row', padding: 10, backgroundColor: '#FFFDF8', borderTopWidth: 1, borderTopColor: '#DDD6C7' },
  input: { flex: 1, borderWidth: 1, borderColor: '#DDD6C7', borderRadius: 6, padding: 10, marginRight: 8 },
  sendButton: { backgroundColor: '#1B2A45', borderRadius: 6, paddingHorizontal: 16, justifyContent: 'center' },
  sendButtonText: { color: '#FFFDF8', fontWeight: '600' },
});
