// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { KeyboardEventHandler, SyntheticEvent, useEffect, useRef, useState } from 'react'
import styleClasses from "./conversation.module.scss"
import { ActionIcon, Group, Textarea, Title, rem, Tooltip, Button, Text } from '@mantine/core'
import { IconArrowRight, IconFileText, IconSquare } from '@tabler/icons-react'
import { conversationSelector, doConversation, getCollections, getMcpList, getAllConversations, getCollectionQuestionList, setIsStreaming } from '../../redux/Conversation/ConversationSlice'
import { ConversationMessage } from '../Message/conversationMessage'
import { useAppDispatch, useAppSelector, clearConversationHistory } from '../../redux/store'
import { Message, MessageRole } from '../../redux/Conversation/Conversation'
import { getCurrentTimeStamp,globalChatState } from '../../common/util'
import { useDisclosure } from '@mantine/hooks'
import DataSource from './DataSource'
import { ConversationSideBar } from './ConversationSideBar'
import { userSelector } from '../../redux/User/userSlice'
import client from "../../common/client";
import { URL_FILE_DOWNLOAD } from '../../config'


type ConversationProps = {
  title: string
}

const Conversation = ({ title }: ConversationProps) => {
  // 基础状态管理
  const [prompt, setPrompt] = useState<string>("")
  const promptInputRef = useRef<HTMLTextAreaElement>(null)
  const [fileUploadOpened, { open: openFileUpload, close: closeFileUpload }] = useDisclosure(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [historyOption, setHistoryOption] = useState<boolean>(false)
  const [placeholder, setPlaceholder] = useState(import.meta.env.VITE_ASK_PLACEHOLDER)
  const [showQuestionList, setShowQuestionList] = useState(false)
  const [questionList, setQuestionList] = useState<string[]>([])
  const [selectedQuestions, setSelectedQuestions] = useState<string[]>([])

  // 会话状态追踪（使用全局变量newChatInitialId）
  // const [isNewChat, setIsNewChat] = useState(true)
  const [hasEverSwitchedToExisting, setHasEverSwitchedToExisting] = useState(false)
  const [prevSessionType, setPrevSessionType] = useState<"new" | "existing">("new")
  const [prevSessionId, setPrevSessionId] = useState("")
  const [isInternalNewChatIdChange, setIsInternalNewChatIdChange] = useState(false)

  // Redux状态获取
  const { 
    conversations, 
    onGoingResult, 
    selectedConversationId, 
    selectedConversationHistory, 
    selectedCollection,
    selectedDynamicOption,
    mcpList, 
    filesTraced, 
    collectionQuestionList, 
    isStreaming 
  } = useAppSelector(conversationSelector)
  const dispatch = useAppDispatch()
  const { name } = useAppSelector(userSelector)
  const selectedConversation = conversations.find(c => c.id === selectedConversationId)

  // 滚动控制
  const scrollViewport = useRef<HTMLDivElement>(null)

  // 1. 核心判断逻辑（使用全局变量newChatInitialId）
  const isCurrentExisting = 
    selectedConversationId !== "" && 
    conversations.some(c => c.id === selectedConversationId) && 
    (globalChatState.newChatInitialId !== "" ? 
      // 已记录新会话初始ID时，当前ID必须不等于新会话ID
      selectedConversationId !== globalChatState.newChatInitialId : 
      // 未记录新会话ID时，排除内部ID变化且必须有历史消息
      false
    );

  const currentSessionType: "new" | "existing" = isCurrentExisting ? "existing" : "new"

  // 2. 会话切换判断
  const isActualSessionSwitch = 
    selectedConversationId !== prevSessionId && 
    !isInternalNewChatIdChange;

  const isSwitchNewToExisting = isActualSessionSwitch && prevSessionType === "new" && currentSessionType === "existing"
  const isSwitchFromExisting = isActualSessionSwitch && prevSessionType === "existing"

  // 3. 输入框禁用条件
  const isInputBoxDisabled = 
    hasEverSwitchedToExisting || 
    isSwitchNewToExisting || 
    isSwitchFromExisting;

  const isSendButtonDisabled = 
    isInputBoxDisabled || 
    !prompt.trim() || 
    selectedCollection === "";

  // 4. 全局变量同步更新（新会话首次生成ID时）
  useEffect(() => {
    if (
      selectedConversationId !== "" && 
      globalChatState.newChatInitialId === "" 
      // && !conversations.some(c => c.id === selectedConversationId)
    ) {
      // 更新全局变量存储新会话初始ID
      globalChatState.newChatInitialId = selectedConversationId;
    }
  }, [selectedConversationId, conversations]);

  // 5. 新会话内部ID变化标记
  useEffect(() => {
    if (
      selectedConversationId !== "" && 
      prevSessionId === "" && 
      !conversations.some(c => c.id === selectedConversationId)
    ) {
      setIsInternalNewChatIdChange(true);
    } else {
      setIsInternalNewChatIdChange(false);
    }
  }, [selectedConversationId, prevSessionId, conversations]);

  // 6. 会话状态重置与更新
  useEffect(() => {
    // 处理真实会话切换
    if (isActualSessionSwitch) {
      if (currentSessionType === "existing") {
        setHasEverSwitchedToExisting(true);
      }
      setPrevSessionType(currentSessionType);
      setPrevSessionId(selectedConversationId);
    }

    // 新建会话时重置所有状态（包括全局变量）
    if (selectedConversationId === "" && selectedConversationHistory.length === 0) {
      globalChatState.newChatInitialId = ""; // 重置全局变量
      setHasEverSwitchedToExisting(false);
      setPrevSessionType("new");
      setPrevSessionId(""); 
      setIsInternalNewChatIdChange(false);
    }
  }, [selectedConversationId, selectedConversationHistory.length, currentSessionType, isActualSessionSwitch, prevSessionId])

  // 7. 初始化数据加载
  useEffect(() => {
    dispatch(getCollectionQuestionList(selectedCollection))
  }, [selectedCollection, dispatch])

  useEffect(() => {
    setQuestionList(collectionQuestionList)
  }, [collectionQuestionList])

  useEffect(() => {
    const numOfShowingQuestions = 5
    if (questionList.length <= numOfShowingQuestions) {
      setSelectedQuestions(questionList)
    } else {
      const shuffled = [...questionList].sort(() => Math.random() - 0.5)
      setSelectedQuestions(shuffled.slice(0, numOfShowingQuestions))
    }
  }, [questionList, selectedConversationId])

  useEffect(() => {
    const refreshCollections = () => dispatch(getCollections(undefined))
    refreshCollections()
    const interval = setInterval(refreshCollections, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [dispatch])

  useEffect(() => {
    dispatch(getMcpList(undefined))
  }, [dispatch])

  useEffect(() => {
    if (name && name !== "" && name !== "Anonymous") {
      dispatch(getAllConversations({ user: name }))
    }
  }, [name, dispatch])

  // 自动滚动到底部
  useEffect(() => {
    scrollViewport.current?.scrollTo({ 
      top: scrollViewport.current.scrollHeight,
      behavior: "smooth"
    })
  }, [onGoingResult, selectedConversationHistory])

  // 8. 交互逻辑
  const handleSubmit = () => {
    const userPrompt: Message = {
      role: MessageRole.User,
      content: prompt,
      time: getCurrentTimeStamp().toString()
    }
    let messages: Message[] = []

    if (conversations.length > 0 && !historyOption) {
      messages = selectedConversationHistory
    }

    abortControllerRef.current = new AbortController()
    dispatch(setIsStreaming(true))

    doConversation({
      conversationId: selectedConversationId,
      userPrompt,
      messages,
      historyOption,
      collectionName: selectedCollection,
      dynamicOption: selectedDynamicOption,
      signal: abortControllerRef.current.signal,
      mcpList: mcpList
    })

    setPrompt("")
    setPlaceholder(import.meta.env.VITE_ASK_PLACEHOLDER)
  }

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      dispatch(setIsStreaming(false))
      abortControllerRef.current = null
    }
  }

  const handleKeyDown: KeyboardEventHandler = (event) => {
    if (!event.shiftKey && event.key === "Enter" && prompt.trim() !== "") {
      if (event.nativeEvent?.isComposing) return
      
      event.preventDefault()
      if (selectedCollection === "") {
        return;
      }
      handleSubmit()
      setTimeout(() => {
        setPrompt("")
      }, 1)
    }
  }

  const handleChange = (event: SyntheticEvent) => {
    event.preventDefault()
    setPrompt((event.target as HTMLTextAreaElement).value)
  }

  const handleQuestionClick = (question: string) => {
    setPlaceholder(question)
    setPrompt(question)
  }

  // 文件缓存逻辑
  useEffect(() => {
    for (const item of filesTraced) {
      if (!item.fileName) continue
      const path = URL_FILE_DOWNLOAD + decodeURIComponent(item.filePath).trim()
      client.get(path).catch(err => console.warn("文件缓存失败:", err))
    }
  }, [filesTraced])

  // 9. 页面渲染
  return (
    <div className={styleClasses.conversationWrapper}>
      {import.meta.env.VITE_FLAG_MINI === "no" && (
        <ConversationSideBar 
          title={title} 
          historyOption={historyOption} 
          setHistoryOption={setHistoryOption}
        />
      )}

      <div className={styleClasses.conversationContent}>
        <div className={styleClasses.conversationContentMessages}>
          <div className={styleClasses.conversationTitle}>
            <Title order={3} className={styleClasses.title}>
              {import.meta.env.VITE_CHAT_TITLE !== "" 
                ? import.meta.env.VITE_CHAT_TITLE 
                : (selectedConversation?.first_query || "New Conversation")} 
            </Title>
            <span className={styleClasses.spacer}></span>
            
            {import.meta.env.VITE_FLAG_MINI === "no" && (
              <Group>
                <Tooltip label="Find files">
                  <ActionIcon 
                    onClick={openFileUpload} 
                    disabled={selectedCollection === ""} 
                    size={32} 
                    variant="default"
                  >
                    <IconFileText />
                  </ActionIcon>
                </Tooltip>
              </Group>
            )}

            {import.meta.env.VITE_FLAG_MINI === "yes" && (
              <Button
                variant="subtle"
                size="xs"
                className={styleClasses.titleButton}
                onClick={() => {
                  clearConversationHistory(selectedConversationId)
                  window.location.reload()
                }}
              >
                {import.meta.env.VITE_CLEAR_HISTORY_BUTTON_TEXT}
              </Button>
            )}
          </div>

          <div className={styleClasses.historyContainer} ref={scrollViewport}>
            {import.meta.env.VITE_FLAG_MINI === "no" && 
              !(selectedConversation || selectedConversationHistory.length > 0) && (
              <div className={styleClasses.infoMessages}>
                <div className="Message">
                  请先选择知识库（或选择 [SKIP]），再输入问题；未选择知识库时可先编辑输入内容。
                </div>
              </div>
            )}

            {questionList.length > 0 && (
              <>
                <Text 
                  onClick={() => setShowQuestionList(!showQuestionList)} 
                  className={styleClasses.faqText}
                >
                  {import.meta.env.VITE_FAQ_TEXT}
                </Text>
                <div className={`${styleClasses.displayQuestionList} ${showQuestionList ? styleClasses.hideQuestionList : ''}`}>
                  {Array.isArray(selectedQuestions) && selectedQuestions.map((question, index) => (
                    <Button 
                      key={index} 
                      onClick={() => handleQuestionClick(question)} 
                      variant="light" 
                      color="blue" 
                      radius="md" 
                      style={{ margin: '5px' }}
                    >
                      {question}
                    </Button>
                  ))}
                </div>
              </>
            )}

            {selectedConversationHistory.map((message, index) => {
              return (
                message.role !== MessageRole.System && 
                <ConversationMessage
                  key={`${index}_ai`}
                  date={message.time ? +message.time * 1000 : getCurrentTimeStamp()}
                  human={message.role === MessageRole.User}
                  message={message.content}
                  onGoingState=""
                  current_references={message.current_references}
                  history_index={index}
                />
              )
            })}

            {onGoingResult && (
              <ConversationMessage
                key="ongoing_ai"
                date={Date.now()}
                human={false}
                message={onGoingResult}
                onGoingState={onGoingResult}
                history_index={-1}
              />
            )}
          </div>

          {/* 输入区域 */}
          <div className={styleClasses.conversationActions}>
            <Textarea
              radius="xl"
              size="md"
              placeholder={placeholder}
              ref={promptInputRef}
              onKeyDown={handleKeyDown}
              onChange={handleChange}
              value={prompt}
              rightSectionWidth={42}
              disabled={isInputBoxDisabled}
              styles={selectedCollection === "" ? { input: { borderColor: '#ff4d4f' } } : {}}
              rightSection={
                <ActionIcon
                  onClick={isStreaming ? handleStop : handleSubmit}
                  size={32}
                  radius="xl"
                  variant="filled"
                  disabled={isSendButtonDisabled}
                >
                  {isStreaming ? (
                    <IconSquare style={{ width: rem(18), height: rem(18) }} stroke={1.5} />
                  ) : (
                    <IconArrowRight style={{ width: rem(18), height: rem(18) }} stroke={1.5} />
                  )}
                </ActionIcon>
              }
            />
          </div>
        </div>
      </div>

      {import.meta.env.VITE_FLAG_MINI === "no" && (
        <DataSource opened={fileUploadOpened} onClose={closeFileUpload} collection={selectedCollection} />
      )}
    </div>
  )
}

export default Conversation
