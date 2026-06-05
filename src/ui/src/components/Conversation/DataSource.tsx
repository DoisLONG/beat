// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0


//import { ActionIcon, Button, Container, Drawer, FileInput, Text, TextInput, Title} from '@mantine/core'
import { Container, Drawer, Text } from '@mantine/core'
//import { IconFile, IconTrash, IconSearch } from '@tabler/icons-react'
import { IconFile } from '@tabler/icons-react'
//import { SyntheticEvent, useState, useEffect } from 'react'
import { useEffect } from 'react'
import { useAppDispatch, useAppSelector } from '../../redux/store'
//import { conversationSelector, submitDataSourceURL, uploadFile, getAllFilesInDataSource, deleteInDataSource } from '../../redux/Conversation/ConversationSlice'
import { conversationSelector, getAllFilesInDataSource } from '../../redux/Conversation/ConversationSlice'
import classes from './dataSource.module.scss'
//import { userNameSelector } from '../../redux/User/userSlice'
//import client from "../../common/client";
//import { useDisclosure } from '@mantine/hooks'

type Props = {
  collection?: string
  opened: boolean
  onClose: () => void
}

export default function DataSource({ opened, onClose, collection}: Props) {
  const title = "Data Source"
  //const [file, setFile] = useState<File[]>();
  //const [isFile, setIsFile] = useState<boolean>(true);
  //const [traceFile, setTraceFile] = useState<boolean>(false);
  //const [collectionName, setCollectionName] = useState<string>("")
  //const [url, setURL] = useState<string>("");
  const dispatch = useAppDispatch()
  const { filesInDataSource } = useAppSelector(conversationSelector)
  //const { filesTraced } = useAppSelector(conversationSelector)
  //const username = useAppSelector(userNameSelector)

  /*
  // comment upload functions for now
  const handleFileUpload = () => {
    if (file && file.length > 0 && collectionName !== "") {
      dispatch(uploadFile({file, collectionName}));
    }
    if (collectionName === "") {
      console.log("Missing dataset collection name while uploading...")
    }
  }

  const handleSetCollection = (event: SyntheticEvent) => {
    event.preventDefault()
    setCollectionName((event.target as HTMLTextAreaElement).value)
  }

  const handleChange = (event: SyntheticEvent) => {
    event.preventDefault()
    setURL((event.target as HTMLTextAreaElement).value)
  }

  const handleSubmit = () => {
    dispatch(submitDataSourceURL({ link_list: url.split(";"), collectionName: collectionName }))
  }

  const handleDelete = (file2delete: string) => {
    if ( collection && collection !== "") {
      dispatch(deleteInDataSource({file: file2delete, collectionName: collection}))
    }
  }
  */

  useEffect(() => {
    if (collection !== "" && collection !== undefined) {
      dispatch(getAllFilesInDataSource({collectionName: collection, knowledgeBaseId: "default"}))
    }
  }, [collection])

  return (
    <div>
      <Drawer title={<span style={{ color: 'black', fontSize: '24px', fontWeight: 'bold', fontFamily: 'Greycliff CF' }}>{title}</span>} size="50%" position="right" opened={opened} onClose={onClose} withOverlay={false}>
        {
          // conceal file upload for now
          /*
        <Text size="sm">
          Please upload your local file or paste a remote file link, and Chat will respond based on the content of the uploaded file. Note that only admin could upload files.
        </Text>

        <Container styles={{
          root: { paddingTop: '40px', display:'flex', flexDirection:'column', alignItems:'center' }
        }}>
          <Button.Group styles={{ group:{alignSelf:'center'}}} >
            <Button variant={isFile ? 'filled' : 'default'} onClick={() => setIsFile(true)}>Upload File</Button>
            <Button variant={!isFile ? 'filled' : 'default'} onClick={() => setIsFile(false)}>Use Link</Button>
          </Button.Group>
        </Container>

        <Container styles={{root:{paddingTop: '40px'}}}>
          <div>
            {isFile ? (
              <>
                <TextInput label="Set DataSet Collection" value={collectionName} onChange={handleSetCollection} disabled={username !== 'admin'} placeholder='Default' description={"Set collection name where the file belongs to."}/>
                <FileInput label="Choose file to upload" value={file} onChange={setFile} placeholder="Choose File" multiple={true} disabled={username !== 'admin'} description={"choose a file to upload for RAG"}/>
                <Button style={{marginTop:'5px'}} onClick={handleFileUpload} disabled={!file || collectionName == "" || username !== 'admin'}>Upload</Button>
              </>
            ) : (
              <>
                <TextInput label="Set DataSet Collection" value={collectionName} disabled={username !== 'admin'} onChange={handleSetCollection} placeholder='Default' description={"Set collection name where the url belongs to."}/>
                <TextInput label="Input URL" value={url} onChange={handleChange} placeholder='URL' disabled={username !== 'admin'} description={"Use semicolons (;) to separate multiple URLs."} />
                  <Button style={{ marginTop: '5px' }} onClick={handleSubmit} disabled={!url || collectionName == "" || username !== 'admin'}>Upload</Button>
              </>
            )}
          </div>
        </Container>
        */
        }

        {// comment padding settings
         //<Container styles={{ root: { paddingTop: '40px' } }}>
        }
        <Container styles={{ root: { marginLeft: '0px' }}}>
          {/*
          <div className={classes.container}>
            <Title order={3} styles={{ root: { margin: '1px', marginBottom: '10px' } }}>
              Files
            </Title>
          </div>
          */}
          {filesInDataSource.map(file=> {
            return (
              <div key={file.name} className={classes.items}>
                <div className={classes.fileicon}><IconFile /></div>
                <div className={classes.filename}><Text size="sm" >{decodeURIComponent(file.name)}</Text></div>
                {/* <div className={classes.icon}>
                  <ActionIcon onClick={()=>handleDelete(decodeURIComponent(file.name))} size={32} variant="default">
                    <IconTrash />
                  </ActionIcon>
                </div> */}
              </div>
            )})
          }
        </Container>
      </Drawer>
    </div>
  )
}
