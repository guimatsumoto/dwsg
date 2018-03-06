# -*- coding: utf-8 -*-

try:
    import cv2
    import torch
except:
    pass

import os
import pickle
import random
import argparse
import torch as t
import numpy as np

from torch.optim import Adam
from torch.utils.data import Dataset, DataLoader
from model import Word2Vec, SkipGramNegSampling


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', type=str, default='sgns', help="model name")
    parser.add_argument('--data_dir', type=str, default='./data/', help="data directory path")
    parser.add_argument('--save_dir', type=str, default='./pts/', help="model directory path")
    parser.add_argument('--e_dim', type=int, default=300, help="embedding dimension")
    parser.add_argument('--n_negs', type=int, default=20, help="number of negative samples")
    parser.add_argument('--epoch', type=int, default=10, help="number of epochs")
    parser.add_argument('--mb', type=int, default=4096, help="mini-batch size")
    parser.add_argument('--ss_t', type=float, default=1e-5, help="subsample threshold")
    parser.add_argument('--conti', action='store_true', help="continue learning")
    parser.add_argument('--weights', action='store_true', help="use weights for negative sampling")
    parser.add_argument('--cuda', action='store_true', help="use CUDA")
    return parser.parse_args()


class PermutedSubsampledCorpus(Dataset):

    def __init__(self, datapath, ws=None):
        with open(datapath, 'rb') as f:
        if ws is not None:
            self.data = []
            for iword, owords in data:
                if random.random() > ws[iword]:
                    self.data.append((iword, owords))
        else:
            self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        iword, owords = self.data[idx]
        return iword, np.array(owords)


def train(args):
    idx2word = pickle.load(open(os.path.join(args.data_dir, 'idx2word.dat'), 'rb'))
    wc = pickle.load(open(os.path.join(args.data_dir, 'wc.dat'), 'rb'))
    wf = np.array([wc[word] for word in idx2word])
    wf = wf / wf.sum()
    ws = 1 - np.sqrt(args.ss_t / wf)
    ws = np.clip(ws, 0, 1)
    vocab_size = len(idx2word)
    weights = wf if args.weights else None
    word2vec = Word2Vec(vocab_size=vocab_size, embedding_size=args.e_dim)
    sgns = SkipGramNegSampling(embedding=word2vec, vocab_size=vocab_size, n_negs=args.n_negs, weights=weights)
    optim = Adam(sgns.parameters())
    if args.cuda:
        sgns = sgns.cuda()
    if not os.path.isdir(args.save_dir):
        os.mkdir(args.save_dir)
    if args.conti:
        sgns.load_state_dict(t.load(os.path.join(args.save_dir, '{}.pt'.format(args.name))))
        optim.load_state_dict(t.load(os.path.join(args.save_dir, '{}.optim.pt'.format(args.name))))
    for epoch in range(1, args.epoch + 1):
        dataset = PermutedSubsampledCorpus(os.path.join(args.data_dir, 'train.dat'))
        dataloader = DataLoader(dataset, batch_size=args.mb, shuffle=True)
        total_batches = int(np.ceil(len(dataset) / args.mb))
        for batch, (iword, owords) in enumerate(dataloader):
            loss = sgns(iword, owords)
            optim.zero_grad()
            loss.backward()
            optim.step()
            print("[e{:2d}][b{:5d}/{:5d}] loss: {:7.4f}\r".format(epoch, batch + 1, total_batches, loss.data[0]), end='\r')
        print("")
    idx2vec = word2vec.ivectors.weight.data.cpu().numpy()
    pickle.dump(idx2vec, open(os.path.join(args.data_dir, 'idx2vec.dat'), 'wb'))
    t.save(sgns.state_dict(), os.path.join(args.save_dir, '{}.pt'.format(args.name)))
    t.save(optim.state_dict(), os.path.join(args.save_dir, '{}.optim.pt'.format(args.name)))


if __name__ == '__main__':
    #train(parse_args())
    data = PermutedSubsampledCorpus('datasets/test_data.txt', [0, 0, 0])
    for k in range(3):
        i, o = data.__getitem__(0)
        print(i)
        print(o)