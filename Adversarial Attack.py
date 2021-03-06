# -*- coding: utf-8 -*-

from google.colab import drive
drive.mount('/content/drive',force_remount=True)

os.getcwd()

"""
Adversary Attack 
"""
# from torchvision import models as tvm
import os
import glob
import torch
import numpy as np
import torch.nn as nn
from PIL import Image
from pathlib import Path
from torch.autograd import Variable
from torch.nn import functional as F
import torchvision.transforms as transforms
import matplotlib.pyplot as plt

class LeNet(nn.Module):
    def __init__(self):
        super(LeNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.conv1_bn = nn.BatchNorm2d(6)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.conv2_bn = nn.BatchNorm2d(16)
        self.fc1   = nn.Linear(16*5*5, 120)
        self.fc1_bn = nn.BatchNorm2d(120)
        self.fc2   = nn.Linear(120, 84)
        self.fc2_bn = nn.BatchNorm2d(84)
        self.fc3   = nn.Linear(84, 10)

    def forward(self, x):
        out = F.relu(self.conv1(x))
        out = F.max_pool2d(out, 2)
        out = F.relu(self.conv2(out))
        out = F.max_pool2d(out, 2)
        out = out.view(out.size(0), -1)
        out = F.relu(self.fc1(out))
        out = F.relu(self.fc2(out))
        out = self.fc3(out)
        return out

class AdversialAttacker(object):

    def __init__(self, method='FGSM'):
        assert method in ['FGSM', 'I-FGSM']
        self.method = method
        print("created adversial attacker in method '%s'" % (method))

    def get_pred_label(self, mdl, inp, ret_out_scores=False, ret_out_pred=True):
        # use current model to get predicted label
        train = mdl.training
        mdl.eval()
        with torch.no_grad():
            out = F.softmax(mdl(inp), dim=1)
        out_score, out_pred = out.max(dim=1)
        if ret_out_scores and not ret_out_pred:
            return out
        if ret_out_pred and not ret_out_scores:
            return out_pred
        mdl.train(train)
        return out_pred, out

    def perturb_untargeted(self, mdl, inp, true_label, targ_label=None, eps=1e-1):
        # perform attacking perturbation in the untargeted setting
        mdl.train()  # switch model to train mode

        if self.method == 'FGSM':
            x = Variable(inp.data, requires_grad=True)
            mdl.eval()
            y=mdl(x)
            loss = nn.CrossEntropyLoss().cuda()
            loss=loss(y,torch.Tensor([true_label]).long())
            mdl.zero_grad()
            loss.backward()
            x_grad = x.grad.detach()
            x_grad_sign = x_grad.sign()
            x=x+eps*x_grad_sign
            clampobj=Clamp()
            torch.clamp(x, 0., 1.)
            pass

        elif self.method == 'I-FGSM':
          x = Variable(inp.data, requires_grad=True)
          xcopy=x
          iterations=5
          alpha=eps/iterations
          for it in range(iterations):
            mdl.eval()
            y=mdl(x)
            loss = nn.CrossEntropyLoss().cuda()
            loss=loss(y,torch.Tensor([true_label]).long())
            mdl.zero_grad()
            loss.backward()
            x_grad = x.grad.detach()
            x_grad_sign = x_grad.sign()
            x=x+alpha*x_grad_sign
            x[x > xcopy + eps] = xcopy[x > xcopy + eps] + eps
            x[x < xcopy - eps] = xcopy[x < xcopy - eps] - eps
            x = Variable(x.data, requires_grad=True)
            torch.clamp(x, 0., 1.)
          pass

        mdl.eval()  # switch model back
        # return the attacked image tensor
        return x

    def perturb_targeted(self, mdl, inp, targ_label, eps=0.03):
        # perform attacking perturbation in the targeted setting
        mdl.train()  # switch model to train mode

        if self.method == 'FGSM':
            x = Variable(inp.data, requires_grad=True)
            mdl.eval()
            y=mdl(x)
            loss = nn.CrossEntropyLoss().cuda()
            loss=loss(y,torch.Tensor(targ_label).long())
            mdl.zero_grad()
            loss.backward()
            x_grad = x.grad.detach()
            x_grad_sign = x_grad.sign()
            x=x-eps*x_grad_sign
            clampobj=Clamp()
            torch.clamp(x, 0., 1.)
            pass

        elif self.method == 'I-FGSM':
          x = Variable(inp.data, requires_grad=True)
          xcopy=x
          iterations=5
          alpha=eps/iterations
          for it in range(iterations):
            mdl.eval()
            y=mdl(x)
            loss = nn.CrossEntropyLoss().cuda()
            loss=loss(y,torch.Tensor(targ_label).long())
            mdl.zero_grad()
            loss.backward()
            x_grad = x.grad.detach()
            x_grad_sign = x_grad.sign()
            x=x-alpha*x_grad_sign
            x[x > xcopy + eps] = xcopy[x > xcopy + eps] + eps
            x[x < xcopy - eps] = xcopy[x < xcopy - eps] - eps
            x = Variable(x.data, requires_grad=True)
            torch.clamp(x, 0., 1.)
            pass

        mdl.eval()  # switch model back
        # return the attacked image tensor
        return x

class Clamp:
    def __call__(self, inp):
        return torch.clamp(inp, 0., 1.)

def generate_experiment(img_path,method='FGSM'):

    device = torch.device('cuda')
    model=LeNet()
    model.load_state_dict(torch.load(os.getcwd()+"/drive/My Drive/AparnaCV/cinicmodel", map_location=device))


    # cinic class names
    import yaml
    with open(os.getcwd()+'/drive/My Drive/AparnaCV/cinic_classnames.yml', 'r') as fp:
        classnames = yaml.safe_load(fp)

    # load image
    input_img = Image.open(img_path)

    # define normalizer and un-normalizer for images
    # cinic dataset
    mean = [0.47889522, 0.47227842, 0.43047404]
    std = [0.24205776, 0.23828046, 0.25874835]

    tf_img = transforms.Compose(
        [
            # transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=mean,
                std=std
            )
        ]
    )
    un_norm = transforms.Compose(
        [
            transforms.Normalize(
                mean=[-m/s for m, s in zip(mean, std)],
                std=[1/s for s in std]
            ),
            Clamp(),
            transforms.ToPILImage()
        ]
    )

    # To be used for iterative method
    # to ensure staying within Linf limits
    clip_min = min([-m/s for m, s in zip(mean, std)])
    clip_max = max([(1-m)/s for m, s in zip(mean, std)])

    input_tensor = tf_img(input_img)
    attacker = AdversialAttacker(method=method)

    return {
        'img': input_img,
        'inp': input_tensor.unsqueeze(0),
        'attacker': attacker,
        'mdl': model,
        'clip_min': clip_min,
        'clip_max': clip_max,
        'un_norm': un_norm,
        'classnames': classnames
    }

#RUN CODE

# Commented out IPython magic to ensure Python compatibility.
# %load_ext autoreload
# %autoreload 2
# %matplotlib inline
target_label=[0,1,2,3,4,5,6,7,8,9]    
Untargeted=False                                    
# Image path
img_path=os.getcwd()+'/drive/My Drive/AparnaCV/Data/train/'
labels=['airplane','automobile','bird','cat','deer','dog','frog','horse','ship','truck']
tot=[]

for i in labels:
  if(i=='airplane'):
    true_label=0
  elif(i=='automobile'):
    true_label=1
  elif(i=='bird'):
    true_label=2
  elif(i=='cat'):
    true_label=3
  elif(i=='deer'):
    true_label=4
  elif(i=='dog'):
    true_label=5
  elif(i=='frog'):
    true_label=6
  elif(i=='horse'):
    true_label=7
  elif(i=='ship'):
    true_label=8
  elif(i=='truck'):
    true_label=9

for label in labels:
  if Untargeted==False:
    fig=plt.figure(figsize=(10,10))
  fooled=0;
  notfooled=0;
  folder=img_path+label
  count=0
  for filename in glob.glob(folder+'/*.png'):
    count=count+1
    # create experiment case
    x = generate_experiment(filename,method='FGSM')

    input_img    = x['img']
    input_tensor = x['inp']
    attacker     = x['attacker']
    model        = x['mdl']
    un_norm      = x['un_norm']
    classnames   = x['classnames']

    # run the classifier model
    out_pred, scores = attacker.get_pred_label(model, input_tensor, ret_out_scores=True, ret_out_pred=True)


    top_scores, top_indices = scores.topk(5)


    # now let's attack
    if Untargeted==True:
      # untargeted setting
      inp_adv = attacker.perturb_untargeted(model,input_tensor, true_label, eps=5)

      # check the image after attacking
      img_adv = un_norm(inp_adv.squeeze(0))
      

      # visualize the perturbation "directly"
      def diff_img(img1, img2,scale=1):
          return Image.fromarray(
              scale * np.abs(
                  np.array(img1).astype('float') - np.array(img2).astype('float')
              ).astype(np.uint8)
          )

      img_diff = diff_img(img_adv, un_norm(input_tensor.squeeze(0)), scale=1) 


      # run classifier again for the attacked image
      attacked_pred, attacked_score = attacker.get_pred_label(model, inp_adv, ret_out_scores=True, ret_out_pred=True)


      top_attacked_scores, top_attacked_indices = attacked_score.topk(5)
    

      print("\nDid we fooled the classifier?")
      if int(attacked_pred) != int(out_pred):
          print(' - Yes!')
          fooled=fooled+1
      else:
          print(' - Nah.')
          notfooled=notfooled+1
      if count==100:
        break

    if Untargeted==False: #Targeted Case
        # # targeted setting
        for target in target_label:
          print("current target",target)
          # target_label = 7

          ax = fig.add_subplot(1,10,target+1)
          
          inp_adv = attacker.perturb_targeted(model, input_tensor, targ_label=[target], eps=0.5)
          # check the image after attacking
          img_adv = un_norm(inp_adv.squeeze(0))
          # print("Image after attacking")
          # plt.imshow(np.array(np.transpose(img_adv,(0,1,2))))
          # plt.show()

          # visualize the perturbation "directly"
          def diff_img(img1, img2,scale=1):
              return Image.fromarray(
                  scale * np.abs(
                      np.array(img1).astype('float') - np.array(img2).astype('float')
                  ).astype(np.uint8)
              )

          img_diff = diff_img(img_adv, un_norm(input_tensor.squeeze(0)), scale=1) 
          # print("Visualizing perturbation directly",img_diff)


          # run classifier again for the attacked image
          attacked_pred, attacked_score = attacker.get_pred_label(model, inp_adv, ret_out_scores=True, ret_out_pred=True)


          top_attacked_scores, top_attacked_indices = attacked_score.topk(5)

          print("\nDid we fooled the classifier?")
          
          if int(attacked_pred) != int(out_pred):
              print(' - Yes!')
              fooled=fooled+1

              ax.imshow(np.array(np.transpose(img_adv,(0,1,2))))

          else:
              print(' - Nah.')
              notfooled=notfooled+1

              ax.imshow(np.zeros((32,32)))

        if count==1:
          break
        plt.show()
  print("Class ",label,"Percentage fooled ",fooled/(fooled+notfooled))
  print("Percentage not fooled",notfooled/(fooled+notfooled))
  tot.append(fooled/(fooled+notfooled))
print("Percentage Fooled in 1000 images",sum(tot)/len(tot))

