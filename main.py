# -*- coding: utf-8 -*-
"""nli-preprocess.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1ZgKZ9KxttNREqU8WFUyEjnkrg8MDcqxO
"""
CUDA_LAUNCH_BLOCKING=1
import pandas as pd
import numpy as np
import os
import re
import torch
import torch.nn as nn
import torch.nn.functional as F
import json
# !pip install transformers
from transformers import DataProcessor, InputExample, InputFeatures

bert_model_type = 'bert-base-uncased'
from transformers import BertTokenizer
tokenizer = BertTokenizer.from_pretrained(bert_model_type)
cls_token = tokenizer.cls_token
sep_token = tokenizer.sep_token
pad_token = tokenizer.pad_token
unk_token = tokenizer.unk_token
print(cls_token, sep_token, pad_token, unk_token)

cls_token_idx = tokenizer.cls_token_id
sep_token_idx = tokenizer.sep_token_id
pad_token_idx = tokenizer.pad_token_id
unk_token_idx = tokenizer.unk_token_id
print(cls_token_idx, sep_token_idx, pad_token_idx, unk_token_idx)

label_conversion = {'n':0, #neutral
'e':1, #entailment
'c':2} #contradiction

max_input_length = tokenizer.max_model_input_sizes[bert_model_type]
print(max_input_length)

# BATCH_SIZE = 16
BATCH_SIZE = 1

def read_jsonl(path):
    with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
            return [json.loads(line) for line in lines]

def create_examples(filename):
        """Creates examples for the training, dev and test sets."""
        examples = []

        data = read_jsonl(filename)
        for (i, line) in enumerate(data):
            guid = "%s-%s" % ("anli-bert-tf", i)
            premise = line['context'] 
            hypothesis = line['hypothesis']
            label = line['label']
            examples.append(InputExample(guid=guid, text_a=premise, text_b=hypothesis, label=label))
        return examples

#Get list of 0s 
def get_sent1_token_type(sent):
    try:
        return [0]* len(sent)
    except:
        return []
#Get list of 1s
def get_sent2_token_type(sent):
    try:
        return [1]* len(sent)
    except:
        return []

def pad_sequence(sequence, max_seq_length=max_input_length, pad_token=pad_token):
    ''' 
    Pads the sequence to the max_seq_length.
    '''
    #sequence = sequence.split(" ")
    sequence = sequence[:max_seq_length]
    sequence = sequence + [pad_token]*(max_seq_length - len(sequence))
    return sequence

def pad_attention_mask(attention_mask, max_seq_length=max_input_length):
    ''' 
    Pads the attention mask to the max_seq_length.
    '''
    #attention_mask = attention_mask.split(" ")
    attention_mask = attention_mask[:max_seq_length]
    attention_mask = attention_mask + [0]*(max_seq_length - len(attention_mask))
    return attention_mask


def pad_token_type(token_type, max_seq_length=max_input_length):
    ''' 
    Pads the token type to the max_seq_length.
    '''
    #token_type = token_type.split(" ")
    token_type = token_type[:max_seq_length]
    token_type = token_type + [1]*(max_seq_length - len(token_type))
    return token_type

def split_and_cut(sentence):
    tokens = sentence.strip().split(" ")
    tokens = tokens[:max_input_length]
    return tokens

def convert_list_to_str(token):
    return ''.join(str(e) for e in token)
    
def convert_to_int(token):
    return [int(x) for x in token]


def preprocess_data_for_bert(path, max_seq_length=max_input_length, tokenizer=tokenizer):
    ''' 
    Preprocesses the anli jsonl data for BERT.
    '''
    dataset = create_examples(path)
    df = pd.DataFrame(columns=['label', 'sequence', 'attention_mask', 'token_type', 'sentence1', 'sentence2'])
    for i, example in enumerate(dataset):
        sent1 = tokenizer.tokenize(example.text_a)
        sent1 = [cls_token] + sent1 + [sep_token]
        sent2 = tokenizer.tokenize(example.text_b)
        sent2 = sent2 + [sep_token]
        final_sent = sent1 + sent2
        label = example.label
        attention_mask = [1]*len(final_sent)
        #attention_mask = convert_list_to_str(attention_mask)
        token_type = get_sent1_token_type(sent1)+ get_sent2_token_type(sent2)
        #token_type = convert_list_to_str(token_type)
        #final_sent = " ".join(final_sent)
        final_sent = pad_sequence(final_sent)
        final_sent = tokenizer.convert_tokens_to_ids(final_sent)
        attention_mask = pad_attention_mask(attention_mask)
        token_type = pad_token_type(token_type)
        df.loc[i] = [np.array(label_conversion[label]), np.array(final_sent), np.array(attention_mask), np.array(token_type), np.array(sent1), np.array(sent2)]
        #df.loc[i] = [label, final_sent, attention_mask, token_type, sent1, sent2]

    return df

# !ls

df_T = preprocess_data_for_bert("./data/anli_v1.0/anli_v1.0/R3/train.jsonl")
# df_T = preprocess_data_for_bert("./data/train.jsonl")

df_T.head()

def convert_to_tuples(df):
    '''
    Converts the dataframe to list of tuples.
    '''
    ds = []
    for index, row in df.iterrows():
        ds.append((row['label'], row['sequence'], row['attention_mask'], row['token_type']))
    
    return ds

from torch.utils.data import Dataset, DataLoader, RandomSampler, SequentialSampler

class BertAnliProcessor():
    """Processor for the ANLI data set."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        # self.dev_data = 
        self.train_data = preprocess_data_for_bert(data_dir+"train.jsonl")
        # self.dev_data = preprocess_data_for_bert(data_dir+"dev.jsonl")
        # self.test_data = preprocess_data_for_bert(data_dir+"test.jsonl")
        self.train_data.to_csv(data_dir+"train_processed.csv", index=False)
        # self.dev_data.to_csv(data_dir+"dev_processed.csv", index=False)
        # self.test_data.to_csv(data_dir+"test_processed.csv", index=False)

    def get_train_dataloader(self):
        """
        Formats the train data into a DataLoader.
        tuple : (label, sequence, attention_mask, token_type)
        """
        ds = convert_to_tuples(self.train_data)
        loader = DataLoader(ds, batch_size=BATCH_SIZE, shuffle=True)
        return loader

    def get_dev_dataloader(self):
        """
        Formats the dev data into a DataLoader.
        tuple : (label, sequence, attention_mask, token_type)
        """
        ds = convert_to_tuples(self.dev_data)
        loader = DataLoader(ds, batch_size=BATCH_SIZE, shuffle=True)
        return loader


    def get_test_dataloader(self):
        """
        Formats the test data into a DataLoader.
        tuple : (label, sequence, attention_mask, token_type)
        """
        ds = convert_to_tuples(self.test_data)
        loader = DataLoader(ds, batch_size=BATCH_SIZE, shuffle=True)
        return loader

obj = BertAnliProcessor('./data/anli_v1.0/anli_v1.0/R1/')

loader = obj.get_train_dataloader()

x = next(iter(loader))
# for batch_idx, label, sequence, attention_mask, token_type in enumerate(loader):
#     print(label)
#     print(sequence)
#     print(attention_mask)
#     print(token_type)
#     # print(batch_idx)
#     # print(sequence)
#     # print(attn_mask)
#     # print(token_type)

print(x)

from transformers import BertModel
bert_model = BertModel.from_pretrained('bert-base-uncased',output_hidden_states=True)

import torch.nn as nn
import numpy as np

import torch
import torch.nn as nn
# from jutils import *

## cubic
# lowersize = 40
# hiddensize = 6

## Gaussian
# lowersize = 20
# hiddensize = 8

## club vs l1out
lowersize = 40
hiddensize = 8

class CLUBv2(nn.Module):  # CLUB: Mutual Information Contrastive Learning Upper Bound
    def __init__(self, x_dim, y_dim, lr=1e-3, beta=0):
        super(CLUBv2, self).__init__()
        self.hiddensize = y_dim
        self.version = 2
        self.beta = beta

    def mi_est_sample(self, x_samples, y_samples):
        sample_size = y_samples.shape[0]
        random_index = torch.randint(sample_size, (sample_size,)).long()

        positive = torch.zeros_like(y_samples)
        negative = - (y_samples - y_samples[random_index]) ** 2 / 2.
        upper_bound = (positive.sum(dim=-1) - negative.sum(dim=-1)).mean()
        # return upper_bound/2.
        return upper_bound

    def mi_est(self, x_samples, y_samples):  # [nsample, 1]
        positive = torch.zeros_like(y_samples)

        prediction_1 = y_samples.unsqueeze(1)  # [nsample,1,dim]
        y_samples_1 = y_samples.unsqueeze(0)  # [1,nsample,dim]
        negative = - ((y_samples_1 - prediction_1) ** 2).mean(dim=1) / 2.   # [nsample, dim]
        return (positive.sum(dim=-1) - negative.sum(dim=-1)).mean()
        # return (positive.sum(dim = -1) - negative.sum(dim = -1)).mean(), positive.sum(dim = -1).mean(), negative.sum(dim = -1).mean()

    def loglikeli(self, x_samples, y_samples):
        return 0

    def update(self, x_samples, y_samples, steps=None):
        # no performance improvement, not enabled
        if steps:
            beta = self.beta if steps > 1000 else self.beta * steps / 1000  # beta anealing
        else:
            beta = self.beta

        return self.mi_est_sample(x_samples, y_samples) * self.beta

club = CLUBv2(x_dim=10,y_dim = 10, beta=5e-3).cuda()

class BERTNLIModel(nn.Module):
    def __init__(self,

                 bert_model,

                 hidden_dim,

                 output_dim,

                ):
        super().__init__()
        self.bert = bert_model
        embedding_dim = bert_model.config.to_dict()['hidden_size']
        self.out = nn.Linear(embedding_dim, output_dim)
    def forward(self, sequence, attn_mask, token_type):
        # bert_output = self.bert(input_ids = sequence, attention_mask = attn_mask, token_type_ids= token_type)[1]
        bert_output = self.bert(input_ids = sequence, attention_mask = attn_mask, token_type_ids= token_type)
        embedded = bert_output[1]
        output = self.out(embedded)
        hidden_states = bert_output[2]
        first_state = hidden_states[0]
        last_state = hidden_states[-1]
        return (output , first_state, last_state)

  #defining model
HIDDEN_DIM = 512
# OUTPUT_DIM = len(LABEL.vocab)
OUTPUT_DIM = 3
# model = BERTNLIModel(bert_model,
#                          HIDDEN_DIM,
#                          OUTPUT_DIM,
#                         ).to(device)

model = BERTNLIModel(bert_model,
                         HIDDEN_DIM,
                         OUTPUT_DIM,
                        ).cuda()

from transformers import *
import torch.optim as optim
optimizer = AdamW(model.parameters(),lr=2e-5,eps=1e-6,correct_bias=False)
# def get_scheduler(optimizer, warmup_steps):
#     scheduler = get_constant_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps)
#     return scheduler
# criterion = nn.CrossEntropyLoss().to(device)
criterion = nn.CrossEntropyLoss().cuda()
# mp = True
# if mp:
#     try:
#         from apex import amp
#     except ImportError:
#         raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use fp16 training.")
#     model, optimizer = amp.initialize(model, optimizer, opt_level='O1')

def categorical_accuracy(preds, y):
    max_preds = preds.argmax(dim = 1, keepdim = True)

    correct = (max_preds.squeeze(1)==y).float()

    return correct.sum() / len(y)

max_grad_norm = 1
epoch_loss = 0
epoch_acc = 0
model.train()


for batch_idx, samples in enumerate(loader):
    label, sequence, attention_mask, token_type  = samples
    # print(label)
    # print(sequence)
    # print(attention_mask)
    # print(token_type)
    optimizer.zero_grad() # clear gradients first
    torch.cuda.empty_cache() # releases all unoccupied cached memory
    sequence = sequence.cuda()
    attn_mask = attention_mask.cuda()
    token_type = token_type.cuda()
    label = label.cuda()
    predictions , firststate, laststate = model(sequence, attn_mask, token_type)
    # print(firststate.size())
    # print(laststate.size())
    loss1 = criterion(predictions, label)
    loss2= club.update(firststate, laststate)
    loss = loss1 + loss2

    acc = categorical_accuracy(predictions, label)

    loss.backward()
    optimizer.step()
    print(loss)
    # scheduler.step()
    epoch_loss += loss.item()
    epoch_acc += acc.item()
    torch.save(model.state_dict(),"infobertr3")

def train(model, iterator, optimizer, criterion, scheduler):
  epoch_loss = 0
  epoch_acc = 0
  model.train()
  for batch in iterator:
    optimizer.zero_grad() # clear gradients first
    torch.cuda.empty_cache() # releases all unoccupied cached memory
    sequence = batch.sequence
    attn_mask = batch.attention_mask
    token_type = batch.token_type
    label = batch.label
    predictions = model(sequence, attn_mask, token_type)
    loss = criterion(predictions, label)
    acc = categorical_accuracy(predictions, label)
    if mp:
      with amp.scale_loss(loss, optimizer) as scaled_loss:
        scaled_loss.backward()
        torch.nn.utils.clip_grad_norm_(amp.master_params(optimizer), max_grad_norm)
    else:
      loss.backward()
      optimizer.step()
      scheduler.step()
      epoch_loss += loss.item()
      epoch_acc += acc.item()
  return epoch_loss / len(iterator), epoch_acc / len(iterator)